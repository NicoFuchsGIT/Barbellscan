import numpy as np
import pytest

from barbellscan.config import load_analysis, load_bars
from barbellscan.deflection import d1_mm
from barbellscan.detection import detect_balls
from barbellscan.simulate import SimParams, bend_profile, plates_for_load, render
from barbellscan.tracking import draw_overlay, track_image
from barbellscan.validation import compare_to_truth

CFG = load_analysis()
BARS = load_bars()


def _render(bar_id="ohio_deadlift", d1=10.0, seed=1, **kw):
    bar = BARS.model_of(bar_id)
    return render(bar, d1, CFG.support_offset_mm, SimParams(**kw), np.random.default_rng(seed))


def test_bend_profile_hits_requested_d1_and_straight_sleeves():
    bar = BARS.model_of("texas_deadlift")
    x = np.linspace(-bar.total_length_mm / 2, bar.total_length_mm / 2, 2001)
    y = bend_profile(x, bar, CFG.support_offset_mm, 12.0)
    assert y[1000] - y[0] == pytest.approx(12.0, abs=0.02)
    assert y[1000] > 0 > y[0]
    assert y[abs(x - CFG.support_offset_mm).argmin()] == pytest.approx(0.0, abs=0.05)
    sleeves = np.abs(x) > bar.shaft_length_mm / 2 + 20
    assert np.allclose(np.diff(y[sleeves & (x > 0)], 2), 0, atol=1e-6)  # gerade


def test_d1_is_roll_invariant_and_signed():
    ang = np.deg2rad(5)
    rot = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    pts = [np.array(p) for p in ((0.0, 100.0), (1000.0, 100.0), (500.0, 90.0))]  # Mitte 10 px oben
    base = d1_mm(*(tuple(p) for p in pts), 1.0)
    rolled = d1_mm(*(tuple(rot @ p) for p in pts), 1.0)
    assert base == pytest.approx(10.0)
    assert rolled == pytest.approx(10.0)
    assert d1_mm((0, 100), (1000, 100), (500, 110), 2.0) == pytest.approx(-5.0)


@pytest.mark.parametrize("d1", [0.0, 3.0, 18.0, 35.0])
def test_tracking_recovers_known_deflection(d1):
    res = _render(d1=d1, roll_deg=0.4)
    row = track_image(res.image)
    assert row["quality_flags"] == ""
    assert row["d1_mm"] == pytest.approx(d1, abs=0.25)
    assert row["scale_px_per_mm"] == pytest.approx(1.0, rel=0.01)


def test_ball_centroids_match_truth_to_subpixel():
    res = _render(d1=12.0, roll_deg=0.3)
    balls = detect_balls(res.image)
    for name in ("left", "right"):
        assert np.allclose(balls[name][0], res.points_px[name], atol=0.15)


def test_plates_do_not_disturb_tracking():
    res = _render("ohio_power", d1=6.0, plates_per_side=4, roll_deg=0.3)
    row = track_image(res.image)
    assert row["quality_flags"] == ""
    assert row["d1_mm"] == pytest.approx(6.0, abs=0.25)


def test_hanging_balls_shift_d1_by_hang_length_and_can_be_corrected():
    """Hängende Kugeln senken die Sehne um h => D1 + h; mit bekanntem h korrigierbar."""
    img = _render(d1=15.0, ball_hang_mm=40.0).image
    assert track_image(img)["d1_mm"] == pytest.approx(55.0, abs=0.25)
    assert track_image(img, ball_hang_mm=40.0)["d1_mm"] == pytest.approx(15.0, abs=0.25)


def test_aruco_in_other_depth_plane_biases_scale():
    """Parallaxe-Risiko: Markerebene 5 % weiter weg => Skala 5 % zu klein => D1 5 % zu groß."""
    row = track_image(_render(d1=20.0, aruco_scale_ratio=0.95).image)
    assert row["d1_mm"] == pytest.approx(20.0 / 0.95, rel=0.01)


def test_plates_for_load_matches_protocol():
    assert [plates_for_load(x) for x in (20, 75, 125, 225, 425)] == [0, 1, 2, 4, 8]


def test_missing_markers_are_flagged_not_raised():
    img = _render("ohio_power", d1=8.0).image.copy()
    img[:, : img.shape[1] // 4] = 225  # linke Kugel auslöschen
    row = track_image(img)
    assert "missing_ball" in row["quality_flags"]
    assert np.isnan(row["d1_mm"])
    img2 = _render("ohio_power", d1=8.0).image.copy()
    img2[: img2.shape[0] // 4, :] = 225  # ArUco auslöschen
    assert "missing_aruco" in track_image(img2)["quality_flags"]


def test_compare_to_truth_reports_small_bias(tmp_path):
    from barbellscan.simulate import generate_dataset
    from barbellscan.tracking import track_manifest

    cfg = CFG.model_copy(update={"loads_kg": [20.0, 225.0, 425.0], "runs": 1})
    truth = generate_dataset(tmp_path, BARS, cfg, only_bars=["texas_power"], n_jobs=1)
    stats = compare_to_truth(track_manifest(tmp_path / "manifest.csv", n_jobs=1), truth)
    assert stats["detection_rate"] == 1.0
    assert abs(stats["bias_mm"]) < 0.15 and stats["rmse_mm"] < 0.2


def test_overlay_draws_without_error():
    img = _render("ohio_power", d1=8.0).image
    out = draw_overlay(img, track_image(img))
    assert out.shape == img.shape and (out != img).any()
