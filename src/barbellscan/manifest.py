"""Manifest: Zuordnung Bilddatei <-> Stange, Run, Last (FR-01, FR-02)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .config import AnalysisConfig, BarCatalog

COLUMNS = ["bar_id", "run", "load_kg", "is_baseline", "image_path", "image_sha256"]


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def expected_design(bars: BarCatalog, cfg: AnalysisConfig) -> pd.DataFrame:
    """Soll-Design: eine Zeile pro erwartetem Bild (bar_id, run, load_kg, is_baseline)."""
    rows = []
    for bar_id in bars.bar_ids():
        for run in range(1, cfg.runs + 1):
            rows += [(bar_id, run, load, False) for load in cfg.loads_kg]
            if cfg.baseline_after_unload:
                rows.append((bar_id, run, cfg.loads_kg[0], True))
    return pd.DataFrame(rows, columns=["bar_id", "run", "load_kg", "is_baseline"])


def check_manifest(manifest: pd.DataFrame, bars: BarCatalog, cfg: AnalysisConfig) -> list[str]:
    """Gibt eine Liste von Problemen zurück (leer = vollständig und konsistent)."""
    problems: list[str] = []
    missing_cols = set(COLUMNS) - set(manifest.columns)
    if missing_cols:
        return [f"Fehlende Spalten: {sorted(missing_cols)}"]

    key = ["bar_id", "run", "load_kg", "is_baseline"]
    for dup in manifest[manifest.duplicated(key, keep=False)].itertuples():
        problems.append(f"Doppelter Eintrag: {dup.bar_id} run {dup.run} {dup.load_kg} kg")
    if manifest["image_path"].duplicated().any():
        problems.append("Eine Bilddatei ist mehreren Einträgen zugeordnet")

    expected = expected_design(bars, cfg)
    merged = expected.merge(manifest[key], on=key, how="outer", indicator=True)
    for r in merged[merged["_merge"] == "left_only"].itertuples():
        problems.append(f"Fehlt: {r.bar_id} run {r.run} {r.load_kg} kg baseline={r.is_baseline}")
    for r in merged[merged["_merge"] == "right_only"].itertuples():
        problems.append(
            f"Unerwartet: {r.bar_id} run {r.run} {r.load_kg} kg baseline={r.is_baseline}"
        )
    return problems
