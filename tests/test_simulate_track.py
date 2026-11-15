import numpy as np
import pandas as pd
import pytest

from barbellscan.config import load_analysis, load_bars
from barbellscan.deflection import add_deflection, bar_summary, chord_offset_px, cycle_summary
from barbellscan.detection import roi_px
from barbellscan.simulate import SimParams, bend_profile, render
from barbellscan.tracking import draw_overlay, track_image
from barbellscan.validation import compare_to_truth

BARS = load_bars()
CFG = load_analysis()
# Synthetik: 1 px/mm, keine ROI (die echte ROI gilt für 6000 x 3376 px Fotos)
SIM_CFG = CFG.model_copy(
    update={
        "detection": CFG.detection.model_copy(update={"nominal_px_per_mm": 1.0, "roi_frac": None})
    }
)


def _render(bar_id="ohio_deadlift", d1=40.0, seed=1, **kw):
    return render(BARS.bar(bar_id), d1, CFG.geometry, SimParams(**kw), np.random.default_rng(seed))


def _track(res, bar_id):
    return track_image(res.image, BARS.bar(bar_id), SIM_CFG)


def test_bend_profile_hits_requested_d1_and_straight_sleeves():
    bar = BARS.bar("texas_deadlift")
    end = bar.total_length_mm / 2 + 35
    x = np.linspace(-end, end, 4001)
    y = bend_profile(x, bar, 362.5, 12.0, end)
    assert y[2000] - y[0] == pytest.approx(12.0, abs=0.02)
    assert y[2000] > 0 > y[0]
    assert y[abs(x - 362.5).argmin()] == pytest.approx(0.0, abs=0.05)
    sleeves = x > bar.shaft_length_mm / 2 + 20
    assert np.allclose(np.diff(y[sleeves], 2), 0, atol=1e-6)  # gerade


def test_chord_offset_is_roll_invariant_and_signed():
    ang = np.deg2rad(5)
    rot = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    pts = [np.array(p) for p in ((0.0, 100.0), (1000.0, 100.0), (500.0, 90.0))]  # Mitte 10 px oben
    assert chord_offset_px(*(tuple(p) for p in pts)) == pytest.approx(10.0)
    assert chord_offset_px(*(tuple(rot @ p) for p in pts)) == pytest.approx(10.0)
    assert chord_offset_px((0, 100), (1000, 100), (500, 110)) == pytest.approx(-10.0)


@pytest.mark.parametrize(
    ("bar_id", "d1", "plates"),
    [("ohio_power", 0.0, 0), ("ohio_power", 70.0, 8), ("texas_deadlift", 105.0, 8),
     ("zkc_iwf", 30.0, 4), ("texas_squat", 60.0, 6)],
)  # fmt: skip
def test_tracking_recovers_deflection_and_ring_scale(bar_id, d1, plates):
    res = _render(bar_id, d1, plates_per_side=plates, roll_deg=0.5, shift_px=(3.3, -2.1))
    row = _track(res, bar_id)
    assert row["detect_flags"] == ""
    scale = row["ring_dist_px"] / BARS.bar(bar_id).ring_spacing_mm
    assert scale == pytest.approx(1.0, rel=0.001)
    assert row["d1_px"] / scale == pytest.approx(d1, abs=0.2)
    assert row["dring_px"] / scale == pytest.approx(res.dring_mm, abs=0.2)


def test_marker_centroids_match_truth_to_subpixel():
    res = _render("texas_deadlift", 80.0, plates_per_side=6, roll_deg=0.3)
    row = _track(res, "texas_deadlift")
    for name, truth in res.points_px.items():
        assert np.allclose((row[f"{name}_x"], row[f"{name}_y"]), truth, atol=0.15), name


def test_monolift_knobs_are_ignored_without_roi():
    res = _render("ohio_power", 20.0, distractors=True)
    row = _track(res, "ohio_power")
    assert row["detect_flags"] == ""
    assert row["centre_y"] == pytest.approx(res.points_px["centre"][1], abs=0.2)


def test_missing_ball_is_flagged_and_rest_is_found():
    res = _render("ohio_deadlift", 30.0, plates_per_side=2)
    img = res.image.copy()
    lx, ly = (int(round(v)) for v in res.points_px["left"])
    img[ly - 15 : ly + 16, lx - 15 : lx + 16] = 25  # Kugel entfernt (Kappe schwarz)
    row = track_image(img, BARS.bar("ohio_deadlift"), SIM_CFG)
    assert row["detect_flags"] == "missing_left"
    assert np.isnan(row["d1_px"]) and not np.isnan(row["dring_px"])
    assert not np.isnan(row["right_x"])


def test_missing_ring_falls_back_to_balls_and_centre():
    res = _render("ohio_power", 30.0)
    img = res.image.copy()
    rx, ry = (int(round(v)) for v in res.points_px["ring_left"])
    img[ry - 25 : ry + 26, rx - 15 : rx + 16] = 150  # Ringband überklebt (Stahlgrau)
    row = track_image(img, BARS.bar("ohio_power"), SIM_CFG)
    assert "missing_ring" in row["detect_flags"]
    assert row["d1_px"] == pytest.approx(30.0, abs=0.3)
    assert np.isnan(row["ring_dist_px"])


def test_roi_excludes_regions_outside():
    assert roi_px((3376, 6000, 3), CFG.detection.roi_frac) == (0, 1350, 6000, 2363)
    res = _render("ohio_power", 20.0)
    cfg = SIM_CFG.model_copy(
        update={"detection": SIM_CFG.detection.model_copy(update={"roi_frac": (0, 0, 1, 0.2)})}
    )
    row = track_image(res.image, BARS.bar("ohio_power"), cfg)
    assert "missing_ring" in row["detect_flags"] and np.isnan(row["d1_px"])


def _sim_cycle(bar_id, c, d0, cycle="A", shift=(0, 0), seed=0):
    rows = []
    for s in CFG.schedule():
        res = _render(bar_id, d0 + c * s.added_mass_kg, seed + s.step,
                      plates_per_side=s.plates_per_side, shift_px=shift, roll_deg=0.4)  # fmt: skip
        rows.append(
            {"bar_id": bar_id, "cycle": cycle, "step": s.step, "phase": s.phase,
             "added_mass_kg": s.added_mass_kg, **_track(res, bar_id)}
        )  # fmt: skip
    return rows


def test_delta_d1_removes_prebend_and_camera_shift_and_recovers_compliance():
    c = 0.17  # mm/kg
    rows = _sim_cycle("ohio_power", c, d0=4.0, cycle="A", shift=(0, 0))
    rows += _sim_cycle("ohio_power", c, d0=-3.0, cycle="B", shift=(6.0, -9.0), seed=100)
    df = add_deflection(pd.DataFrame(rows), BARS, CFG)
    assert (df["deflection_flags"] == "").all()
    assert df["px_per_mm"].to_numpy() == pytest.approx(1.0, rel=0.002)
    truth = c * df["added_mass_kg"]
    assert np.abs(df["delta_d1_mm"] - truth).max() < 0.25
    cyc = cycle_summary(df, CFG)
    assert cyc["compliance_mm_per_100kg"].to_numpy() == pytest.approx(17.0, rel=0.005)
    assert np.abs(cyc["residual_mm"]).max() < 0.25
    assert np.abs(cyc["hysteresis_mm"]).max() < 0.15
    assert np.abs(cyc["nonlin_at_peak_mm"]).max() < 0.3
    assert cyc["implied_length_mm"].to_numpy() == pytest.approx(2198, abs=2)
    per_bar = bar_summary(cyc, BARS)
    assert per_bar.loc[0, "n_cycles"] == 2
    assert per_bar.loc[0, "stiffness_kg_per_mm"] == pytest.approx(1 / c, rel=0.005)


def test_end_to_end_synthetic_dataset(tmp_path):
    from barbellscan.config import load_analysis
    from barbellscan.simulate import generate_dataset
    from barbellscan.tracking import track_manifest

    cfg = CFG.model_copy(update={"cycles": ["A"], "max_plates_per_side": 2})
    truth = generate_dataset(tmp_path, BARS, cfg, only_bars=["texas_power"], n_jobs=1)
    sim_cfg = load_analysis(tmp_path / "analysis.yaml")
    assert sim_cfg.detection.roi_frac is None
    tracked = track_manifest(tmp_path / "manifest.csv", BARS, sim_cfg, n_jobs=1)
    stats = compare_to_truth(add_deflection(tracked, BARS, sim_cfg), truth)
    assert stats["detection_rate"] == 1.0
    assert abs(stats["delta_d1_bias_mm"]) < 0.15 and stats["delta_d1_rmse_mm"] < 0.25


def test_overlay_draws_without_error():
    res = _render("ohio_power", 8.0)
    out = draw_overlay(res.image, _track(res, "ohio_power"), width=1000)
    assert out.shape[1] == 1000 and out.shape[0] > res.image.shape[0] * 1000 / res.image.shape[1]
