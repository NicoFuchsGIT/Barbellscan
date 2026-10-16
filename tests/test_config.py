import pytest
from pydantic import ValidationError

from barbellscan.config import AnalysisConfig, load_analysis, load_bars


def test_catalog_matches_draft_table_1():
    cat = load_bars()
    assert len(cat.bars) == 13
    cats = [b.category for b in cat.bars]
    assert cats.count("power") == 9
    assert cats.count("deadlift") == 3
    assert cats.count("squat") == 1


def test_two_squat_replicates_give_14_physical_bars():
    ids = load_bars().bar_ids()
    assert len(ids) == 14
    assert {"texas_squat_1", "texas_squat_2"} <= set(ids)


def test_model_of_resolves_replicates():
    cat = load_bars()
    assert cat.model_of("texas_squat_2").model_id == "texas_squat"
    assert cat.model_of("ohio_power").category == "power"


def test_analysis_defaults():
    cfg = load_analysis()
    assert cfg.loads_kg[0] == 20 and cfg.loads_kg[-1] == 425 and len(cfg.loads_kg) == 9
    assert cfg.images_per_bar_run() == 10


def test_loads_must_ascend():
    with pytest.raises(ValidationError):
        AnalysisConfig(loads_kg=[75, 20], runs=5, support_offset_mm=371)
