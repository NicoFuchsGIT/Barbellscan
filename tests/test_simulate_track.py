import numpy as np
import pytest

from barbellscan.config import load_analysis, load_bars
from barbellscan.deflection import d1_mm
from barbellscan.simulate import SimParams, bend_profile, render
from barbellscan.tracking import track_image
from barbellscan.validation import compare_to_truth

CFG = load_analysis()
BARS = load_bars()


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
    bar = BARS.model_of("ohio_deadlift")
    res = render(bar, d1, CFG.support_offset_mm, SimParams(roll_deg=0.4), np.random.default_rng(1))
    row = track_image(res.image)
    assert row["quality_flags"] == ""
    assert row["d1_mm"] == pytest.approx(d1, abs=0.25)
    assert row["scale_px_per_mm"] == pytest.approx(1.0, rel=0.01)


def test_missing_marker_is_flagged_not_raised():
    bar = BARS.model_of("ohio_power")
    img = render(bar, 8.0, CFG.support_offset_mm).image.copy()
    img[:, : img.shape[1] // 4] = 225  # linken Marker auslöschen
    row = track_image(img)
    assert "missing_left" in row["quality_flags"]
    assert np.isnan(row["d1_mm"])


def test_compare_to_truth_reports_small_bias(tmp_path):
    from barbellscan.simulate import generate_dataset
    from barbellscan.tracking import track_manifest

    cfg = CFG.model_copy(update={"loads_kg": [20.0, 225.0, 425.0], "runs": 1})
    truth = generate_dataset(tmp_path, BARS, cfg, only_bars=["texas_power"], n_jobs=1)
    stats = compare_to_truth(track_manifest(tmp_path / "manifest.csv", n_jobs=1), truth)
    assert stats["detection_rate"] == 1.0
    assert abs(stats["bias_mm"]) < 0.15 and stats["rmse_mm"] < 0.2


def test_overlay_draws_without_error():
    from barbellscan.tracking import draw_overlay

    img = render(BARS.model_of("ohio_power"), 8.0, CFG.support_offset_mm).image
    out = draw_overlay(img, track_image(img))
    assert out.shape == img.shape and (out != img).any()
