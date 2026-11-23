from pathlib import Path

import pandas as pd

from barbellscan.config import load_analysis, load_bars
from barbellscan.manifest import check_manifest, expected_design, from_qc_csv

BARS, CFG = load_bars(), load_analysis()


def _full_manifest():
    d = expected_design(BARS, CFG)
    d["image_path"] = [f"img_{i}.jpg" for i in range(len(d))]
    d["image_sha256"] = "0" * 64
    return d


def test_expected_design_size_is_663():
    assert len(expected_design(BARS, CFG)) == 13 * 3 * 17


def test_complete_manifest_has_no_problems():
    assert check_manifest(_full_manifest(), BARS, CFG) == []


def test_missing_duplicate_and_wrong_mass_are_reported():
    m = _full_manifest()
    m.loc[3, "added_mass_kg"] = 999
    m = pd.concat([m.iloc[1:], m.iloc[[5]]], ignore_index=True)
    problems = check_manifest(m, BARS, CFG)
    assert any(p.startswith("Fehlt") for p in problems)
    assert any(p.startswith("Doppelter") for p in problems)
    assert any(p.startswith("added_mass_kg passt nicht") for p in problems)


def test_committed_manifest_is_complete():
    path = Path(__file__).parents[1] / "data" / "manifest.csv"
    m = pd.read_csv(path, dtype={"cycle": str})
    assert check_manifest(m, BARS, CFG) == []
    assert m["image_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()


def test_from_qc_csv_maps_names_and_drops_obsolete_flags():
    qc = pd.DataFrame(
        {
            "photo_bar": ["Eleiko2016PowerTraining", "ZKCIWF"],
            "run_letter": ["B", "C"],
            "step": [0, 9],
            "plates_per_side": [0, 7],
            "image_path": ["Eleiko2016PowerTrainingB0010.JPG", "ZKCIWFC0001.JPG"],
            "image_sha256": ["a" * 64, "b" * 64],
            "exif_datetime": ["2018-01-01 05:38:40", "2018-01-01 07:34:09"],
            "focal_mm": [41.0, 41.0],
            "sharpness_rel": [1.0, 0.3],
            "quality_flags": ["bar_not_in_config;blur", None],
        }
    )
    m = from_qc_csv(qc, BARS, CFG)
    assert list(m["bar_id"]) == ["eleiko_training_2016", "zkc_iwf"]
    assert list(m["added_mass_kg"]) == [0.0, 355.0]
    assert list(m["phase"]) == ["up", "down"]
    assert list(m["qc_flags"]) == ["blur", ""]
    assert m.loc[0, "image_path"] == "raw/Eleiko2016PowerTrainingB0010.JPG"
