import pandas as pd

from barbellscan.config import load_analysis, load_bars
from barbellscan.manifest import check_manifest, expected_design


def _full_manifest():
    d = expected_design(load_bars(), load_analysis())
    d["image_path"] = [f"img_{i}.jpg" for i in range(len(d))]
    d["image_sha256"] = "0" * 64
    return d


def test_expected_design_size_is_700():
    assert len(expected_design(load_bars(), load_analysis())) == 14 * 5 * 10


def test_complete_manifest_has_no_problems():
    assert check_manifest(_full_manifest(), load_bars(), load_analysis()) == []


def test_missing_and_duplicate_are_reported():
    m = _full_manifest()
    m = pd.concat([m.iloc[1:], m.iloc[[5]]], ignore_index=True)
    problems = check_manifest(m, load_bars(), load_analysis())
    assert any(p.startswith("Fehlt") for p in problems)
    assert any(p.startswith("Doppelter") for p in problems)
