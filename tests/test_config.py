import pytest
from pydantic import ValidationError

from barbellscan.config import Detection, load_analysis, load_bars


def test_catalog_matches_analysis_plan():
    cat = load_bars()
    assert len(cat.bars) == 13
    cats = [b.category for b in cat.bars]
    assert (cats.count("power"), cats.count("deadlift")) == (8, 3)
    assert (cats.count("squat"), cats.count("weightlifting")) == (1, 1)
    assert cat.bar("zkc_iwf").ring_spacing_mm == 910
    assert cat.by_prefix("Eleiko2016PowerTraining").bar_id == "eleiko_training_2016"
    assert cat.by_prefix("StrengthShopDeadlift").bar_id == "bastard_deadlift"


def test_ball_span_is_length_plus_two_offsets():
    bar = load_bars().bar("eleiko_comp_2026")
    assert bar.ball_span_mm(35.0) == pytest.approx(2270.0)


def test_schedule_up_and_down_with_added_mass():
    cfg = load_analysis()
    steps = cfg.schedule()
    assert len(steps) == 17 and cfg.peak_step == 8 and cfg.final_step == 16
    masses = [s.added_mass_kg for s in steps]
    assert masses[:9] == [0, 55, 105, 155, 205, 255, 305, 355, 405]
    assert masses[9:] == masses[:8][::-1]
    assert [s.phase for s in steps].count("up") == 9


def test_geometry_from_manuscript():
    g = load_analysis().geometry
    assert g.support_offset_loaded_mm == pytest.approx(362.5)
    assert (g.ball_diameter_mm, g.ball_offset_mm) == (15, 35)


def test_roi_must_be_ordered():
    with pytest.raises(ValidationError):
        Detection(roi_frac=(0.5, 0.2, 0.4, 0.8))
