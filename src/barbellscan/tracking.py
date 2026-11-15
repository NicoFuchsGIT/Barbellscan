"""Pipeline pro Bild: Marker-Detektion -> Pixelgrößen; parallel über das Manifest.

Ergebnis je Bild (alles in Pixeln, Vollbild-Koordinaten der Originaldatei):
Markerpositionen, Kugel- und Ringabstand, ``d1_px`` (Mitte zur Kugel-Sehne) und ``dring_px``
(Mitte zur Ringband-Sehne). Die Umrechnung in mm und der Bezug auf Stufe 0 erfolgen erst in
:mod:`barbellscan.deflection`, weil die Skala je Zyklus aus den Baseline-Fotos kommt.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .config import AnalysisConfig, Bar, BarCatalog
from .deflection import chord_offset_px
from .detection import MARKERS, TAPES, detect_markers, roi_px
from .manifest import resolve_image

RESULT_COLUMNS = [
    *(f"{m}_{c}" for m in MARKERS for c in ("x", "y")),
    "ball_dist_px",
    "ring_dist_px",
    "d1_px",
    "dring_px",
    # Sensitivitätsanalyse: Bänder über den Schwerpunkt der gelben Fläche statt Schaftachse
    *(f"{m}_{c}" for m in TAPES for c in ("cx", "cy")),
    "d1_px_centroid",
    "dring_px_centroid",
    "detect_flags",
]


def _pt(row: dict, name: str) -> tuple[float, float]:
    return row[f"{name}_x"], row[f"{name}_y"]


def _valid(*pts) -> bool:
    return not any(np.isnan(v) for p in pts for v in p)


def track_image(image: np.ndarray, bar: Bar, cfg: AnalysisConfig, full_frame: bool = False) -> dict:
    """Wertet ein Bild aus; fehlende Marker führen zu NaN und einem Flag, nie zu einem Fehler."""
    params = cfg.detection
    if full_frame:
        params = params.model_copy(update={"roi_frac": None})
    g = cfg.geometry
    found = detect_markers(
        image,
        bar.ring_spacing_mm,
        bar.ball_span_mm(g.ball_offset_mm),
        params,
        g.ball_diameter_mm,
        bar.shaft_diameter_mm,
        g.tape_thickness_mm,
    )
    row: dict = dict.fromkeys(RESULT_COLUMNS, np.nan)
    for name, blob in found.points.items():
        if blob is not None:
            row[f"{name}_x"], row[f"{name}_y"] = blob.xy
            if name in TAPES and blob.centroid_xy is not None:
                row[f"{name}_cx"], row[f"{name}_cy"] = blob.centroid_xy
    left, right, centre = _pt(row, "left"), _pt(row, "right"), _pt(row, "centre")
    rl, rr = _pt(row, "ring_left"), _pt(row, "ring_right")
    if _valid(left, right):
        row["ball_dist_px"] = float(np.hypot(right[0] - left[0], right[1] - left[1]))
    if _valid(rl, rr):
        row["ring_dist_px"] = float(np.hypot(rr[0] - rl[0], rr[1] - rl[1]))
    if _valid(left, right, centre):
        row["d1_px"] = chord_offset_px(left, right, centre)
    if _valid(rl, rr, centre):
        row["dring_px"] = chord_offset_px(rl, rr, centre)
    cc = (row["centre_cx"], row["centre_cy"])
    rlc, rrc = (
        (row["ring_left_cx"], row["ring_left_cy"]),
        (row["ring_right_cx"], row["ring_right_cy"]),
    )
    if _valid(left, right, cc):
        row["d1_px_centroid"] = chord_offset_px(left, right, cc)
    if _valid(rlc, rrc, cc):
        row["dring_px_centroid"] = chord_offset_px(rlc, rrc, cc)
    row["detect_flags"] = ";".join(found.flags)
    return row


def _track_path(path: Path, bar: Bar, cfg: AnalysisConfig, full_frame: bool, overlay_out):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return {**dict.fromkeys(RESULT_COLUMNS, np.nan), "detect_flags": "unreadable_image"}
    row = track_image(image, bar, cfg, full_frame)
    if overlay_out is not None:
        roi = None if full_frame else cfg.detection.roi_frac
        Path(overlay_out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(overlay_out), draw_overlay(image, row, roi, title=Path(path).name))
    return row


def track_manifest(
    manifest_path: Path,
    bars: BarCatalog,
    cfg: AnalysisConfig,
    n_jobs: int = -1,
    full_frame: bool = False,
    image_root: Path | None = None,
    overlay_dir: Path | None = None,
) -> pd.DataFrame:
    """Alle Bilder des Manifests auswerten (Bildpfade relativ zum Manifest-Ordner)."""
    manifest_path = Path(manifest_path)
    manifest = pd.read_csv(manifest_path, dtype={"cycle": str})
    base = manifest_path.parent

    def overlay_path(p: str):
        return None if overlay_dir is None else Path(overlay_dir) / (Path(p).stem + "_qc.jpg")

    rows = Parallel(n_jobs=n_jobs)(
        delayed(_track_path)(
            resolve_image(base, r.image_path, image_root),
            bars.bar(r.bar_id),
            cfg,
            full_frame,
            overlay_path(r.image_path),
        )
        for r in manifest.itertuples()
    )
    return pd.concat([manifest, pd.DataFrame(rows, columns=RESULT_COLUMNS)], axis=1)


# --------------------------------------------------------------------------- QC-Overlay

_COLOURS = {
    "left": (255, 128, 0),
    "right": (255, 128, 0),
    "ring_left": (255, 255, 0),
    "ring_right": (255, 255, 0),
    "centre": (0, 0, 255),
}


def draw_overlay(
    image: np.ndarray,
    row: dict,
    roi_frac=None,
    width: int = 1800,
    crop_half_px: int | None = None,
    title: str = "",
) -> np.ndarray:
    """QC-Bild: verkleinerte Gesamtansicht mit Sehnen + vergrößerte Ausschnitte je Marker.

    Die Ausschnitte zeigen den gefundenen Zentroid als Fadenkreuz in Originalauflösung.
    """
    h, w = image.shape[:2]
    f = width / w
    small = cv2.resize(image, (width, int(round(h * f))), interpolation=cv2.INTER_AREA)

    def sp(p):
        return int(round(p[0] * f)), int(round(p[1] * f))

    x0, y0, x1, y1 = roi_px(image.shape, roi_frac)
    cv2.rectangle(small, sp((x0, y0)), sp((x1 - 1, y1 - 1)), (90, 90, 90), 1)
    pts = {m: _pt(row, m) for m in MARKERS}
    for a, b, col in (("left", "right", (0, 200, 0)), ("ring_left", "ring_right", (200, 200, 0))):
        if _valid(pts[a], pts[b]):
            cv2.line(small, sp(pts[a]), sp(pts[b]), col, 1, cv2.LINE_AA)
    if _valid(pts["left"], pts["right"], pts["centre"]):
        a, b, c = (np.asarray(pts[k], float) for k in ("left", "right", "centre"))
        u = (b - a) / np.linalg.norm(b - a)
        foot = a + u * float((c - a) @ u)
        cv2.line(small, sp(c), sp(foot), (0, 0, 255), 2, cv2.LINE_AA)
    for m, p in pts.items():
        if _valid(p):
            cv2.circle(small, sp(p), 7, _COLOURS[m], 2, cv2.LINE_AA)
    text = f"{title}  d1={row.get('d1_px', np.nan):.1f}px  flags: {row.get('detect_flags') or '-'}"
    cv2.putText(small, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(
        small, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA
    )

    c = crop_half_px or max(16, int(round(0.012 * w)))
    tile = width // len(MARKERS)
    tiles = []
    for m in MARKERS:
        t = np.full((tile, tile, 3), 60, np.uint8)
        p = pts[m]
        if _valid(p):
            cx, cy = p
            m_aff = np.float32([[tile / (2 * c), 0, tile / 2 - cx * tile / (2 * c)],
                                [0, tile / (2 * c), tile / 2 - cy * tile / (2 * c)]])  # fmt: skip
            t = cv2.warpAffine(image, m_aff, (tile, tile), flags=cv2.INTER_NEAREST)
            mid = tile // 2
            cv2.line(t, (mid, 0), (mid, tile), _COLOURS[m], 1)
            cv2.line(t, (0, mid), (tile, mid), _COLOURS[m], 1)
        label = m if _valid(p) else f"{m}: fehlt"
        cv2.putText(t, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        tiles.append(t)
    strip = np.hstack(tiles)
    strip = cv2.copyMakeBorder(strip, 0, 0, 0, width - strip.shape[1], cv2.BORDER_CONSTANT)
    return np.vstack([small, strip])
