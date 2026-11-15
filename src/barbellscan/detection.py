"""Marker-Detektion im Originalbild (ANALYSIS_PLAN Abschnitt 4).

Alle Marker sind gelb: zwei Kugeln (Ø 15 mm) an den Kappen, ein Band in der Stangenmitte und
zwei Bänder auf den Ringmarkierungen. Zuordnung über die Geometrie, nicht über die Blobgröße:

1. Gelbe Blobs in der ROI suchen (Fragmente eines Bandes werden zusammengefasst).
2. Ringbänder + Mittenband: drei fast kollineare Blobs, Mitte genau zwischen den äußeren,
   Abstand der äußeren ≈ Ringabstand x nominaler Maßstab (± Toleranz).
3. Kugeln: je Seite der Blob, der der aus dem Ringabstand vorhergesagten Kugelposition
   (Kugelabstand L + 70 mm) am nächsten liegt, innerhalb eines Suchfensters unterhalb der
   Ringlinie (Enden hängen herab).

Fehlt ein Marker, bleibt er leer und wird geflaggt; es wird nie ein Fehler ausgelöst.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import Detection

MARKERS = ("left", "ring_left", "centre", "ring_right", "right")


@dataclass
class Blob:
    xy: tuple[float, float]
    mass: float
    area: int


@dataclass
class Markers:
    points: dict[str, Blob | None] = field(default_factory=lambda: dict.fromkeys(MARKERS))
    flags: list[str] = field(default_factory=list)


def yellow_weight(image: np.ndarray) -> np.ndarray:
    """Gelbanteil je Pixel, (min(R, G) - B) / 255, linear in der Flächenabdeckung."""
    img = image.astype(np.float32)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    return (np.minimum(r, g) - b) / 255.0


def roi_px(shape: tuple[int, ...], roi_frac) -> tuple[int, int, int, int]:
    h, w = shape[:2]
    if roi_frac is None:
        return 0, 0, w, h
    x0, y0, x1, y1 = roi_frac
    return int(round(x0 * w)), int(round(y0 * h)), int(round(x1 * w)), int(round(y1 * h))


def _roi_centroid(
    w: np.ndarray, mask: np.ndarray, pad: int
) -> tuple[tuple[float, float], float] | None:
    """Schwerpunkt ohne Schwellwert in einer Region um den Blob.

    Ein harter Schwellwert würde die Ränder je nach Subpixel-Lage verschieden abschneiden
    (Sägezahn-Fehler mit 1 px Periode); die lineare Gewichtung bleibt dagegen unverzerrt.
    """
    x, y, bw, bh = cv2.boundingRect(mask)
    if bw == 0:
        return None
    h, wd = w.shape
    x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + bw + pad, wd), min(y + bh + pad, h)
    # Negative Gewichte (Stahl, dunkle Flächen) abschneiden; sie würden den Schwerpunkt zur
    # Seite ziehen, die positiven Randanteile bleiben unverändert.
    roi = np.maximum(w[y0:y1, x0:x1].astype(np.float64), 0.0)
    m = cv2.moments(roi)
    if m["m00"] <= 0:
        return None
    return (x0 + m["m10"] / m["m00"], y0 + m["m01"] / m["m00"]), float(m["m00"])


def find_blobs(image: np.ndarray, params: Detection, ball_diameter_mm: float = 15.0) -> list[Blob]:
    """Gelbe Blobs in der ROI mit Subpixel-Zentroid (Vollbild-Koordinaten)."""
    s = params.nominal_px_per_mm
    x0, y0, x1, y1 = roi_px(image.shape, params.roi_frac)
    w = yellow_weight(image[y0:y1, x0:x1])
    mask = (w > params.yellow_threshold).astype(np.uint8)
    merge = max(int(round(1.5 * s)), 1)  # Fragmente (Glanzlichter) zusammenfassen
    joined = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * merge + 1,) * 2))
    n, labels = cv2.connectedComponents(joined, connectivity=8)
    r_min = ball_diameter_mm / 2 * s * (1 - params.scale_tolerance)
    min_area = 0.25 * np.pi * r_min**2
    pad = max(int(round(3 * s)), 3)
    blobs = []
    for i in range(1, n):
        region = ((labels == i) & (mask > 0)).astype(np.uint8)
        area = int(region.sum())
        if area < min_area:
            continue
        res = _roi_centroid(w, region, pad)
        if res is not None:
            (cx, cy), mass = res
            blobs.append(Blob((cx + x0, cy + y0), mass, area))
    return sorted(blobs, key=lambda b: b.xy[0])


def _shaft_triple(blobs: list[Blob], ring_px: float, tol: float):
    """Bestes Tripel (Ring links, Mitte, Ring rechts) oder None."""
    best, best_score = None, np.inf
    for i, a in enumerate(blobs):
        for c in blobs[i + 1 :]:
            span = c.xy[0] - a.xy[0]
            if not (1 - tol) * ring_px <= span <= (1 + tol) * ring_px:
                continue
            if abs(c.xy[1] - a.xy[1]) > 0.05 * span:
                continue
            mid = ((a.xy[0] + c.xy[0]) / 2, (a.xy[1] + c.xy[1]) / 2)
            for b in blobs:
                if b is a or b is c:
                    continue
                ex, ey = abs(b.xy[0] - mid[0]) / span, abs(b.xy[1] - mid[1]) / span
                if ex > 0.04 or ey > 0.06:
                    continue
                score = ex + ey + abs(c.xy[1] - a.xy[1]) / span + abs(span / ring_px - 1) * 0.1
                if score < best_score:
                    best, best_score = (a, b, c), score
    return best


def _find_ball(blobs, used, centre, ring_dir, side: int, half_px: float) -> Blob | None:
    """Kugel einer Seite: nächster Blob zur vorhergesagten Position im Suchfenster."""
    pred = np.asarray(centre) + side * half_px * ring_dir
    normal = np.array([-ring_dir[1], ring_dir[0]])  # zeigt bei ring_dir = (1, 0) nach unten
    best, best_d = None, np.inf
    for b in blobs:
        if any(b is u for u in used):
            continue
        d = np.asarray(b.xy) - pred
        along, down = float(d @ ring_dir), float(d @ normal)
        if abs(along) > 0.06 * half_px or not -0.05 * half_px <= down <= 0.25 * half_px:
            continue
        score = abs(along) + 0.1 * abs(down)
        if score < best_d:
            best, best_d = b, score
    return best


def detect_markers(
    image: np.ndarray,
    ring_spacing_mm: float,
    ball_span_mm: float,
    params: Detection,
    ball_diameter_mm: float = 15.0,
) -> Markers:
    """Sucht die fünf gelben Marker einer Stange mit bekannter Geometrie."""
    out = Markers()
    blobs = find_blobs(image, params, ball_diameter_mm)
    tol = params.scale_tolerance
    triple = _shaft_triple(blobs, ring_spacing_mm * params.nominal_px_per_mm, tol)
    if triple is not None:
        a, b, c = triple
        out.points.update(ring_left=a, centre=b, ring_right=c)
        vec = np.subtract(c.xy, a.xy)
        span = float(np.linalg.norm(vec))
        ring_dir = vec / span
        half_px = ball_span_mm / 2 * span / ring_spacing_mm
        for name, side in (("left", -1), ("right", 1)):
            out.points[name] = _find_ball(blobs, triple, b.xy, ring_dir, side, half_px)
    else:
        out.flags.append("missing_ring")
        _fallback_balls_centre(out, blobs, ball_span_mm * params.nominal_px_per_mm, tol)
    for name in MARKERS:
        if out.points[name] is None and not (
            name.startswith("ring") and "missing_ring" in out.flags
        ):
            out.flags.append(f"missing_{name}")
    return out


def _fallback_balls_centre(out: Markers, blobs: list[Blob], ball_px: float, tol: float) -> None:
    """Ohne Ringbänder: äußerstes Blobpaar mit passendem Abstand als Kugeln, Mitte dazwischen."""
    best, best_score = None, np.inf
    for i, a in enumerate(blobs):
        for c in blobs[i + 1 :]:
            span = c.xy[0] - a.xy[0]
            if (1 - tol) * ball_px <= span <= (1 + tol) * ball_px and abs(
                c.xy[1] - a.xy[1]
            ) < 0.1 * span:
                score = abs(span / ball_px - 1)
                if score < best_score:
                    best, best_score = (a, c), score
    if best is None:
        return
    a, c = best
    out.points.update(left=a, right=c)
    span = c.xy[0] - a.xy[0]
    mid_x = (a.xy[0] + c.xy[0]) / 2
    inner = [b for b in blobs if b is not a and b is not c and abs(b.xy[0] - mid_x) < 0.04 * span]
    if inner:
        out.points["centre"] = min(inner, key=lambda b: abs(b.xy[0] - mid_x))
