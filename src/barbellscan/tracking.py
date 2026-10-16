"""Pipeline pro Bild: Detektion -> Skala -> D1; parallel über das Manifest (M1)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .deflection import d1_mm
from .detection import detect_aruco, detect_tape
from .simulate import MARKER_SIZE_MM

SCALE_MIN_PX_PER_MM = 0.2  # sanity: darunter ist ein Marker zu klein für Subpixel-Genauigkeit


def track_image(image: np.ndarray, detector=None) -> dict:
    """Wertet ein Bild aus; fehlende Marker führen zu NaN und einem Flag, nie zu einem Fehler."""
    hits = detect_aruco(image, detector)
    tape = detect_tape(image)
    flags = []
    if "left" not in hits:
        flags.append("missing_left")
    if "right" not in hits:
        flags.append("missing_right")
    if tape is None:
        flags.append("missing_tape")

    row = {k: np.nan for k in ("left_x", "left_y", "right_x", "right_y", "centre_x", "centre_y")}
    row.update(scale_px_per_mm=np.nan, d1_mm=np.nan)
    if "left" in hits:
        row["left_x"], row["left_y"] = hits["left"].centre_px
    if "right" in hits:
        row["right_x"], row["right_y"] = hits["right"].centre_px
    if tape is not None:
        (row["centre_x"], row["centre_y"]), _ = tape
    if hits:
        row["scale_px_per_mm"] = float(np.mean([h.side_px for h in hits.values()])) / MARKER_SIZE_MM
        if row["scale_px_per_mm"] < SCALE_MIN_PX_PER_MM:
            flags.append("scale_too_small")
    if not flags:
        row["d1_mm"] = d1_mm(
            (row["left_x"], row["left_y"]),
            (row["right_x"], row["right_y"]),
            (row["centre_x"], row["centre_y"]),
            row["scale_px_per_mm"],
        )
    row["quality_flags"] = ";".join(flags)
    return row


def _track_path(path: Path) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return {"quality_flags": "unreadable_image"}
    return track_image(image)


def track_manifest(manifest_path: Path, n_jobs: int = -1) -> pd.DataFrame:
    """Alle Bilder des Manifests auswerten (Bildpfade relativ zum Manifest-Ordner)."""
    manifest_path = Path(manifest_path)
    manifest = pd.read_csv(manifest_path)
    base = manifest_path.parent
    rows = Parallel(n_jobs=n_jobs)(delayed(_track_path)(base / p) for p in manifest["image_path"])
    return pd.concat([manifest, pd.DataFrame(rows)], axis=1)


def draw_overlay(image: np.ndarray, row: dict) -> np.ndarray:
    """QC-Overlay: erkannte Marker und Sehne (Vorläufer von FR-13)."""
    out = image.copy()
    pts = {k: (row[f"{k}_x"], row[f"{k}_y"]) for k in ("left", "right", "centre")}
    if not any(np.isnan(v) for p in pts.values() for v in p):
        ln, rn, cn = (tuple(int(round(v)) for v in pts[k]) for k in ("left", "right", "centre"))
        cv2.line(out, ln, rn, (0, 160, 0), 2, cv2.LINE_AA)
        cv2.line(
            out,
            cn,
            (cn[0], int(round(np.interp(cn[0], [ln[0], rn[0]], [ln[1], rn[1]])))),
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    for p in pts.values():
        if not any(np.isnan(v) for v in p):
            cv2.circle(out, (int(round(p[0])), int(round(p[1]))), 6, (255, 128, 0), 2, cv2.LINE_AA)
    return out
