"""Manifest: Zuordnung Bilddatei <-> Stange, Zyklus, Stufe, Zusatzmasse (FR-01, FR-02).

Schema (eine Zeile pro Foto): ``bar_id, cycle, step, phase, plates_per_side, added_mass_kg,
image_path, image_sha256`` und optional ``exif_datetime, focal_mm, sharpness_rel, qc_flags``.
``image_path`` ist relativ zum Ordner des Manifests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .config import AnalysisConfig, BarCatalog

KEY = ["bar_id", "cycle", "step"]
COLUMNS = [*KEY, "phase", "plates_per_side", "added_mass_kg", "image_path", "image_sha256"]
OPTIONAL = ["exif_datetime", "focal_mm", "sharpness_rel", "qc_flags"]

# Flags aus manifest_qc.csv, die durch die aktuelle Config erledigt sind
_OBSOLETE_QC_FLAGS = {"bar_not_in_config"}


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def expected_design(bars: BarCatalog, cfg: AnalysisConfig) -> pd.DataFrame:
    """Soll-Design: eine Zeile pro erwartetem Foto."""
    rows = [
        (bar_id, cycle, s.step, s.phase, s.plates_per_side, s.added_mass_kg)
        for bar_id in bars.bar_ids()
        for cycle in cfg.cycles
        for s in cfg.schedule()
    ]
    return pd.DataFrame(rows, columns=COLUMNS[:6])


def check_manifest(manifest: pd.DataFrame, bars: BarCatalog, cfg: AnalysisConfig) -> list[str]:
    """Gibt eine Liste von Problemen zurück (leer = vollständig und konsistent)."""
    problems: list[str] = []
    missing_cols = set(COLUMNS) - set(manifest.columns)
    if missing_cols:
        return [f"Fehlende Spalten: {sorted(missing_cols)}"]

    m = manifest.astype({"cycle": str})
    for dup in m[m.duplicated(KEY, keep=False)].itertuples():
        problems.append(f"Doppelter Eintrag: {dup.bar_id} {dup.cycle} step {dup.step}")
    if m["image_path"].duplicated().any():
        problems.append("Eine Bilddatei ist mehreren Einträgen zugeordnet")

    expected = expected_design(bars, cfg)
    merged = expected.merge(m, on=KEY, how="outer", indicator=True, suffixes=("_soll", ""))
    for r in merged[merged["_merge"] == "left_only"].itertuples():
        problems.append(f"Fehlt: {r.bar_id} {r.cycle} step {r.step}")
    for r in merged[merged["_merge"] == "right_only"].itertuples():
        problems.append(f"Unerwartet: {r.bar_id} {r.cycle} step {r.step}")
    both = merged[merged["_merge"] == "both"]
    for col in ("phase", "plates_per_side", "added_mass_kg"):
        bad = both[both[f"{col}_soll"] != both[col]]
        for r in bad.itertuples():
            problems.append(
                f"{col} passt nicht: {r.bar_id} {r.cycle} step {r.step}: "
                f"{getattr(r, col)} statt {getattr(r, col + '_soll')}"
            )
    return problems


def verify_images(manifest: pd.DataFrame, base: Path, image_root: Path | None = None) -> list[str]:
    """Prüft Existenz und SHA-256 jeder Bilddatei (Beweiskette, FR-02)."""
    problems = []
    for r in manifest.itertuples():
        path = resolve_image(base, r.image_path, image_root)
        if not path.exists():
            problems.append(f"Datei fehlt: {path}")
        elif sha256_of(path) != r.image_sha256:
            problems.append(f"SHA-256 weicht ab: {path}")
    return problems


def resolve_image(base: Path, image_path: str, image_root: Path | None = None) -> Path:
    """Bildpfad relativ zum Manifest, oder nur der Dateiname in ``image_root``."""
    if image_root is not None:
        return Path(image_root) / Path(image_path).name
    return Path(base) / image_path


def from_qc_csv(
    qc: pd.DataFrame, bars: BarCatalog, cfg: AnalysisConfig, image_dir: str = "raw"
) -> pd.DataFrame:
    """Übersetzt ``manifest_qc.csv`` (QC vom 15.11.2026) in das Manifest-Schema.

    Die groben Kugelpositionen der QC werden bewusst nicht übernommen (keine Messwerte).
    """
    steps = {s.step: s for s in cfg.schedule()}
    rows = []
    for r in qc.itertuples():
        bar = bars.by_prefix(r.photo_bar)
        s = steps[int(r.step)]
        if int(r.plates_per_side) != s.plates_per_side:
            raise ValueError(f"{r.image_path}: Scheibenzahl {r.plates_per_side} != Soll")
        flags = [
            f
            for f in str(r.quality_flags if pd.notna(r.quality_flags) else "").split(";")
            if f and f not in _OBSOLETE_QC_FLAGS
        ]
        rows.append(
            {
                "bar_id": bar.bar_id,
                "cycle": str(r.run_letter),
                "step": s.step,
                "phase": s.phase,
                "plates_per_side": s.plates_per_side,
                "added_mass_kg": s.added_mass_kg,
                "image_path": f"{image_dir}/{r.image_path}" if image_dir else r.image_path,
                "image_sha256": r.image_sha256,
                "exif_datetime": r.exif_datetime,
                "focal_mm": r.focal_mm,
                "sharpness_rel": r.sharpness_rel,
                "qc_flags": ";".join(flags),
            }
        )
    out = pd.DataFrame(rows, columns=COLUMNS + OPTIONAL)
    order = {b: i for i, b in enumerate(bars.bar_ids())}
    out = out.sort_values(
        ["bar_id", "cycle", "step"], key=lambda c: c.map(order) if c.name == "bar_id" else c
    )
    return out.reset_index(drop=True)
