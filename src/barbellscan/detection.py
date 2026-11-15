"""Marker-Detektion im Originalbild (ANALYSIS_PLAN Abschnitt 4).

Alle Marker sind gelb: zwei Kugeln (Ø 15 mm) an den Kappen, ein Band in der Stangenmitte und
zwei Bänder auf den Ringmarkierungen. Zuordnung über die Geometrie, nicht über die Blobgröße:

1. Gelbe Blobs in der ROI suchen (Fragmente eines Bandes werden zusammengefasst).
2. Ringbänder + Mittenband: drei fast kollineare Blobs, Mitte genau zwischen den äußeren,
   Abstand der äußeren ≈ Ringabstand x nominaler Maßstab (± Toleranz).
3. Kugeln: je Seite der Blob, der der aus dem Ringabstand vorhergesagten Kugelposition
   (Kugelabstand L + 70 mm) am nächsten liegt, innerhalb eines Suchfensters unterhalb der
   Ringlinie (Enden hängen herab).

Messpunkt der Bänder (Mitte, Ringe) ist der **Schwerpunkt der gelben Fläche in der Schaftzone**
(ANALYSIS_PLAN Nachtrag N5): von der Bandoberkante bis Oberkante + Banddurchmesser. Ohne
herabhängendes Bandende ist das der gewöhnliche Schwerpunkt; ein gelöster Lappen liegt
unterhalb der Zone und zählt nicht mit. Zur Sensitivitätsanalyse werden weiter ausgegeben:
der Schwerpunkt der ganzen Fläche (``Blob.centroid_xy``) und die Schaftachse aus der
Oberkante nach Nachtrag N2 (``Blob.axis_xy``; auf den echten Fotos wegen der Glanzlichter auf
den Bändern deutlich unruhiger).

Fehlt ein Marker, bleibt er leer und wird geflaggt; es wird nie ein Fehler ausgelöst.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import Detection

MARKERS = ("left", "ring_left", "centre", "ring_right", "right")
TAPES = ("ring_left", "centre", "ring_right")
CLIP_MARGIN = 0.05  # Schaftzone = Oberkante bis Oberkante + (1 + CLIP_MARGIN) x Banddurchmesser
HANGING_FRACTION = 0.05  # Gelbanteil unterhalb der Schaftzone, ab dem das Band als hängend gilt


@dataclass
class Blob:
    xy: tuple[float, float]  # Messpunkt: Kugelmitte bzw. Band-Schwerpunkt in der Schaftzone
    mass: float
    area: int
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x0, y0, x1, y1 (Vollbild, exklusiv)
    centroid_xy: tuple[float, float] | None = None  # Schwerpunkt der ganzen gelben Fläche
    axis_xy: tuple[float, float] | None = None  # Schaftachse aus der Oberkante (N2)


@dataclass
class TapeFit:
    top_xy: tuple[float, float]  # Bandmittellinie geschnitten mit der Schaftoberkante
    direction: tuple[float, float]  # lokale Schaftrichtung (Einheitsvektor, x > 0)
    height_px: float  # Bandhöhe (80. Perzentil über die Spalten)

    def axis_point(self, radius_px: float) -> tuple[float, float]:
        ux, uy = self.direction
        return self.top_xy[0] - radius_px * uy, self.top_xy[1] + radius_px * ux


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
            bx, by, bw, bh = cv2.boundingRect(region)
            bbox = (bx + x0, by + y0, bx + bw + x0, by + bh + y0)
            blobs.append(Blob((cx + x0, cy + y0), mass, area, bbox, (cx + x0, cy + y0)))
    return sorted(blobs, key=lambda b: b.xy[0])


def _first_crossing(profile: np.ndarray, thr: float) -> float | None:
    """Erste Stelle (Subpixel, Pixelmitten-Koordinaten), an der ``profile`` ``thr`` erreicht."""
    idx = np.flatnonzero(profile >= thr)
    if len(idx) == 0 or idx[0] == 0:
        return None  # kein Rand oder Rand am Ausschnittrand (unzuverlässig)
    i = int(idx[0])
    p0, p1 = float(profile[i - 1]), float(profile[i])
    return i - 1 + (thr - p0) / (p1 - p0)


def _edge_from_area(prof: np.ndarray, i_cross: int, k: int) -> float | None:
    """Kantenlage aus der Fläche unter dem Profil (exakt bei Antialiasing und symmetrischer
    Unschärfe): Kante = Fensterende + 0,5 - Summe(Profil) / Plateau."""
    a, b = i_cross - k, i_cross + k
    if a < 0 or b + 2 * k > len(prof):
        return None
    plateau = float(np.median(prof[b : b + 2 * k]))
    if plateau <= 0:
        return None
    return b + 0.5 - float(prof[a : b + 1].sum()) / plateau


def measure_tape(
    image: np.ndarray, blob: Blob, radius_px: float, scale_px_per_mm: float
) -> TapeFit | None:
    """Oberkante, lokale Neigung und Höhe eines Bandes (ohne den herabhängenden Teil).

    Je Spalte im Inneren des Bandes: Oberkante aus der Fläche unter dem Gelbprofil
    (Subpixel), Unterkante inkl. Lappen grob über den Halbwert. Gerade durch die Oberkanten
    -> Neigung. Die Bandmittellinie kommt aus dem Schwerpunkt der Zone zwischen Oberkante und
    Oberkante + Schaftradius (ein Lappen hängt unterhalb und zählt nicht mit).
    """
    k = max(4, int(round(4 * scale_px_per_mm)))  # halbe Fensterbreite für die Kante (~4 mm)
    pad = 2 * k + 2
    h, w_img = image.shape[:2]
    x0, y0, x1, y1 = blob.bbox
    x0, y0 = max(x0 - pad, 0), max(y0 - pad, 0)
    x1, y1 = min(x1 + pad, w_img), min(y1 + pad, h)
    w = np.maximum(yellow_weight(image[y0:y1, x0:x1]), 0.0).astype(np.float64)
    colmax = w.max(axis=0)
    if colmax.max() <= 0:
        return None
    # Nur Spalten mit vollem Gelbanteil (keine angeschnittenen Bandränder)
    plateau_cols = np.flatnonzero(colmax >= 0.9 * colmax.max())
    rough = {}
    for j in plateau_cols:
        prof = w[:, j]
        cross = _first_crossing(prof, 0.5 * prof.max())
        bottom = _first_crossing(prof[::-1], 0.5 * prof.max())
        if cross is not None and bottom is not None:
            rough[j] = (cross, len(prof) - 1 - bottom)
    if len(rough) < 3:
        return None
    # Oberste Spaltengruppe = Band; Spalten, die nur den herabhängenden Lappen enthalten,
    # beginnen erst an der Bandunterseite und fallen heraus.
    tol = 0.3 * radius_px
    rough_tops = np.array([t for t, _ in rough.values()])
    need = max(3, int(0.3 * len(rough)))
    group_size = [((rough_tops >= t) & (rough_tops <= t + tol)).sum() for t in np.sort(rough_tops)]
    first = next((i for i, n in enumerate(group_size) if n >= need), None)
    if first is None:
        return None
    ref = float(np.sort(rough_tops)[first])
    edge = {}
    for j, (cross, bottom) in rough.items():
        if ref <= cross <= ref + tol:
            top = _edge_from_area(w[:, j], int(np.ceil(cross)), k)
            if top is not None:
                edge[j] = (top, bottom)
    if len(edge) < 3:
        return None
    # Gerade zuerst nur durch die mittlere Hälfte (bei geneigtem Band liegen in den Randspalten
    # die schrägen Seitenkanten), dann alle Spalten, die auf der Geraden liegen.
    cols = np.array(sorted(edge))
    tops_all = np.array([edge[j][0] for j in cols])
    mid, quarter = np.median(cols), max(1.0, (cols.max() - cols.min() + 1) / 4)
    core = np.abs(cols - mid) <= quarter
    if core.sum() < 3:
        core = np.ones_like(cols, bool)
    slope, icpt = np.polyfit(cols[core], tops_all[core], 1)
    on_line = np.abs(tops_all - (icpt + slope * cols)) < 0.5
    if on_line.sum() >= 3:
        slope, icpt = np.polyfit(cols[on_line], tops_all[on_line], 1)
    heights = [edge[j][1] - edge[j][0] for j in cols]
    u = np.array([1.0, slope]) / np.hypot(1.0, slope)
    n_down = np.array([-u[1], u[0]])
    yy, xx = np.mgrid[0 : w.shape[0], 0 : w.shape[1]]
    zone = w * (yy <= icpt + slope * xx + radius_px)
    m = zone.sum()
    if m <= 0:
        return None
    q = np.array([(zone * xx).sum() / m, (zone * yy).sum() / m])
    t = (icpt + slope * q[0] - q[1]) / (n_down[1] - slope * n_down[0])
    top_xy = q + t * n_down
    return TapeFit(
        (float(top_xy[0] + x0), float(top_xy[1] + y0)),
        (float(u[0]), float(u[1])),
        float(np.percentile(heights, 80)),
    )


def clipped_centroid(
    image: np.ndarray, blob: Blob, diameter_px: float
) -> tuple[tuple[float, float], float] | None:
    """Schwerpunkt der gelben Fläche in der Schaftzone und Gelbanteil darunter (Nachtrag N5).

    Oberkante: je Spalte die erste Zeile mit mindestens einem Viertel des Spaltenmaximums,
    davon das 20. Perzentil (Spalten, die nur einen Lappen enthalten, beginnen tiefer). Die
    Zone endet weich (linear über ein Pixel) bei Oberkante + (1 + CLIP_MARGIN) x Durchmesser.
    Die Oberkante muss nur grob stimmen: Sie legt allein die untere Grenze fest und wirkt
    sich auf den Schwerpunkt nur aus, wenn dort tatsächlich ein Lappen hängt.
    """
    pad = max(3, int(round(0.1 * diameter_px)))
    h, w_img = image.shape[:2]
    x0, y0, x1, y1 = blob.bbox
    x0, y0 = max(x0 - pad, 0), max(y0 - pad, 0)
    x1, y1 = min(x1 + pad, w_img), min(y1 + pad, h)
    w = np.maximum(yellow_weight(image[y0:y1, x0:x1]), 0.0).astype(np.float64)
    total = w.sum()
    if total <= 0:
        return None
    colmax = w.max(axis=0)
    cols = np.flatnonzero(colmax >= 0.6 * colmax.max())
    tops = [int(np.argmax(w[:, j] >= 0.25 * colmax[j])) for j in cols]
    limit = float(np.percentile(tops, 20)) + (1 + CLIP_MARGIN) * diameter_px
    rows = np.arange(w.shape[0], dtype=np.float64)[:, None]
    zone = w * np.clip(limit - rows + 0.5, 0.0, 1.0)
    m = zone.sum()
    if m <= 0:
        return None
    cx = float((zone.sum(axis=0) * np.arange(w.shape[1])).sum() / m)
    cy = float((zone.sum(axis=1) * rows[:, 0]).sum() / m)
    return (cx + x0, cy + y0), float(1 - m / total)


def _refine_tapes(
    image: np.ndarray,
    out: Markers,
    radius_mm: float,
    band_mm: float,
    scale0: float,
    ring_spacing_mm: float,
) -> None:
    """Setzt die Messpunkte der Bänder: Schwerpunkt in der Schaftzone (Plan, Nachtrag N5).

    Der Durchmesser in px kommt aus dem Ringabstand im selben Bild (Schwerpunkte), sonst aus
    ``scale0``. Die Schaftachse nach N2 wird als ``axis_xy`` für die Sensitivität mitgeführt.
    """
    scale = scale0
    left, right = out.points["ring_left"], out.points["ring_right"]
    if left is not None and right is not None:
        scale = float(np.hypot(*np.subtract(right.xy, left.xy))) / ring_spacing_mm
    for name in TAPES:
        blob = out.points[name]
        if blob is None:
            continue
        xy = blob.xy
        res = clipped_centroid(image, blob, band_mm * scale)
        if res is not None:
            xy, below = res
            if below > HANGING_FRACTION:
                out.flags.append(f"tape_hanging_{name}")
        fit = measure_tape(image, blob, radius_mm * scale, scale)
        axis = None if fit is None else fit.axis_point(radius_mm * scale)
        out.points[name] = Blob(xy, blob.mass, blob.area, blob.bbox, blob.centroid_xy, axis)


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
    shaft_diameter_mm: float = 29.0,
    tape_thickness_mm: float = 0.0,
) -> Markers:
    """Sucht die fünf gelben Marker einer Stange mit bekannter Geometrie."""
    out = Markers()
    s0 = params.nominal_px_per_mm
    blobs = find_blobs(image, params, ball_diameter_mm)
    tol = params.scale_tolerance
    radius_mm = shaft_diameter_mm / 2 + tape_thickness_mm
    triple = _shaft_triple(blobs, ring_spacing_mm * s0, tol)
    if triple is not None:
        out.points.update(dict(zip(TAPES, triple, strict=True)))
        _refine_tapes(image, out, radius_mm, 2 * radius_mm, s0, ring_spacing_mm)
        a, b, c = (out.points[n] for n in TAPES)
        vec = np.subtract(c.xy, a.xy)
        span = float(np.linalg.norm(vec))
        ring_dir = vec / span
        half_px = ball_span_mm / 2 * span / ring_spacing_mm
        for name, side in (("left", -1), ("right", 1)):
            out.points[name] = _find_ball(blobs, triple, b.xy, ring_dir, side, half_px)
    else:
        out.flags.append("missing_ring")
        _fallback_balls_centre(out, blobs, ball_span_mm * s0, tol)
        left, right = out.points["left"], out.points["right"]
        if left is not None and right is not None:
            scale = float(np.hypot(*np.subtract(right.xy, left.xy))) / ball_span_mm
            _refine_tapes(image, out, radius_mm, 2 * radius_mm, scale, ring_spacing_mm)
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
