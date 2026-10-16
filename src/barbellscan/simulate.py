"""Synthetische Seitenansicht-Bilder mit exakt bekannter Durchbiegung (FR-15, Validierung V1).

Weltkoordinaten in mm: x entlang der Stange (Ursprung = Mitte), y nach oben, y = 0 auf der
Auflagelinie der J-Hooks. Zwischen den Auflagern wölbt sich der Schaft nach oben, die Enden
hängen herab; die Sleeves (starr) bleiben gerade. Zielgröße ist D1 (PRD 5.3): Abstand der
Mitte zur Sehne der beiden Endmarker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from .config import AnalysisConfig, BarCatalog, BarModel

ARUCO_DICT = cv2.aruco.DICT_4X4_50
ARUCO_ID = 0  # einzelner Referenzmarker im Hintergrund (Skala, später Verzerrung)
MARKER_BORDER_MM = 10.0  # weiße Ruhezone um den Marker
BALL_BGR = (0, 215, 255)  # gelbe Kugel an den Sleeve-Kappen (BGR)
TAPE_WIDTH_MM = 40.0
SLEEVE_DIAMETER_MM = 50.0
TAPE_BGR = (255, 0, 255)
PLATE_BGR = (35, 35, 190)  # rote 25-kg-Scheibe
PLATE_EDGE_BGR = (15, 15, 90)
COLLAR_BGR = (45, 45, 45)


@dataclass
class SimParams:
    scale_px_per_mm: float = 1.0
    supersample: int = 4
    blur_sigma_px: float = 0.8
    noise_sigma: float = 2.0
    roll_deg: float = 0.0
    brightness: float = 1.0
    height_mm: float = 600.0
    margin_mm: float = 60.0
    origin_frac: float = 0.5  # Lage der Auflagelinie von oben
    aruco_size_mm: float = 100.0  # Kantenlänge des Hintergrundmarkers
    aruco_offset_mm: float = 140.0  # Höhe des Markermittelpunkts über der Auflagelinie
    aruco_scale_ratio: float = 1.0  # Abbildungsmaßstab der Markerebene relativ zur Stangenebene
    ball_diameter_mm: float = 50.0
    ball_hang_mm: float = 0.0  # Kugelmittelpunkt hängt so weit unter dem Sleeve-Ende
    plates_per_side: int = 0  # 25-kg-Scheiben je Seite (0 = leere Stange)
    plate_thickness_mm: float = 28.0  # ANNAHME, am echten Satz nachmessen
    plate_diameter_mm: float = 450.0
    collar_width_mm: float = 30.0  # ANNAHME
    collar_height_mm: float = 90.0  # ANNAHME


@dataclass
class SimResult:
    image: np.ndarray
    d1_mm: float
    scale_px_per_mm: float
    points_px: dict[str, tuple[float, float]] = field(default_factory=dict)


def bend_profile(
    x_mm: np.ndarray, bar: BarModel, support_offset_mm: float, d1_mm: float
) -> np.ndarray:
    """Höhe y(x) der Stangenachse bei gegebenem D1.

    Krümmung konstant zwischen den Auflagern, danach linear auf 0 am Schaftende abfallend,
    Sleeves starr (gerade, Steigung wie am Schaftende).
    """
    a = support_offset_mm
    xs = bar.shaft_length_mm / 2.0
    half = bar.total_length_mm / 2.0
    dx = 0.5
    grid = np.arange(0.0, half + dx, dx)
    kappa = np.where(
        grid <= a, 1.0, np.where(grid <= xs, 1.0 - (grid - a) / max(xs - a, 1e-9), 0.0)
    )
    theta = np.concatenate([[0.0], np.cumsum((kappa[1:] + kappa[:-1]) / 2 * dx)])
    y = np.concatenate([[0.0], np.cumsum((theta[1:] + theta[:-1]) / 2 * dx)])
    y = -y  # Hogging: Mitte oben, Enden unten
    y -= np.interp(a, grid, y)  # y(Auflager) = 0
    unit_d1 = y[0] - y[-1]
    y = y * (d1_mm / unit_d1)
    return np.interp(np.abs(x_mm), grid, y)


def _blend_rect(canvas: np.ndarray, x0: float, x1: float, y0: float, y1: float, bgr) -> None:
    """Achsenparalleles Rechteck mit exakter Flächenabdeckung je Pixel (Pixelmitten-Koordinaten).

    ``cv2.fillPoly`` füllt das Innere ohne Antialiasing und rastet Kanten auf das Gitter ein.
    """
    ix0, ix1 = int(np.floor(x0 - 0.5)), int(np.ceil(x1 + 0.5))
    iy0, iy1 = int(np.floor(y0 - 0.5)), int(np.ceil(y1 + 0.5))
    xs = np.arange(ix0, ix1 + 1)
    ys = np.arange(iy0, iy1 + 1)
    cov_x = np.clip(np.minimum(xs + 0.5, x1) - np.maximum(xs - 0.5, x0), 0.0, 1.0)
    cov_y = np.clip(np.minimum(ys + 0.5, y1) - np.maximum(ys - 0.5, y0), 0.0, 1.0)
    alpha = (cov_y[:, None] * cov_x[None, :])[..., None]
    roi = canvas[iy0 : iy1 + 1, ix0 : ix1 + 1].astype(np.float32)
    canvas[iy0 : iy1 + 1, ix0 : ix1 + 1] = np.round(
        roi * (1.0 - alpha) + np.array(bgr, np.float32) * alpha
    ).astype(np.uint8)


def _paste_marker(canvas: np.ndarray, patch: np.ndarray, cx: float, cy: float) -> None:
    """Marker-Patch mit Subpixel-Versatz (bilinear) um (cx, cy) in die Leinwand setzen.

    Koordinaten im Pixelmitten-Format (Pixel j liegt bei Koordinate j).
    """
    p = patch.shape[0]
    tlx, tly = cx - (p - 1) / 2.0, cy - (p - 1) / 2.0
    ix, iy = int(np.floor(tlx)), int(np.floor(tly))
    fx, fy = tlx - ix, tly - iy
    roi = np.full((p + 2, p + 2, 3), 255, np.uint8)
    roi[1:-1, 1:-1] = patch
    m = np.float32([[1, 0, fx], [0, 1, fy]])
    roi = cv2.warpAffine(
        roi, m, (p + 2, p + 2), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )
    canvas[iy - 1 : iy + p + 1, ix - 1 : ix + p + 1] = roi


def _stack_polygon(xs_mm, ys_mm, x_c, width_mm, height_mm, to_px, s) -> np.ndarray:
    """Rechteck (Breite entlang der Achse, Höhe senkrecht dazu) um den Achspunkt bei x_c."""
    y_c = float(np.interp(x_c, xs_mm, ys_mm))
    slope = float(np.interp(x_c, xs_mm, np.gradient(ys_mm, xs_mm)))
    u = np.array([1.0, slope]) / np.hypot(1.0, slope)
    v = np.array([-u[1], u[0]])
    c = np.array([x_c, y_c])
    corners = [
        c + a * u * width_mm / 2 + b * v * height_mm / 2
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    return np.array([to_px(*q) for q in corners])


def _fill(canvas, poly, fill, edge, edge_px) -> None:
    sub = np.round(poly * 16).astype(np.int32)
    cv2.fillPoly(canvas, [sub], fill, lineType=cv2.LINE_AA, shift=4)
    cv2.polylines(
        canvas, [sub], True, edge, thickness=max(int(edge_px), 1), lineType=cv2.LINE_AA, shift=4
    )


def _draw_plates(canvas, bar, xs_mm, ys_mm, p: SimParams, to_px, s) -> None:
    x0 = bar.shaft_length_mm / 2.0 + 5.0  # Anschlag am inneren Sleeve-Ende
    t = p.plate_thickness_mm
    for sign in (-1.0, 1.0):
        for k in range(p.plates_per_side):
            xc = sign * (x0 + (k + 0.5) * t)
            poly = _stack_polygon(xs_mm, ys_mm, xc, t, p.plate_diameter_mm, to_px, s)
            _fill(canvas, poly, PLATE_BGR, PLATE_EDGE_BGR, 1.0 * p.supersample)
        xc = sign * (x0 + p.plates_per_side * t + p.collar_width_mm / 2)
        poly = _stack_polygon(xs_mm, ys_mm, xc, p.collar_width_mm, p.collar_height_mm, to_px, s)
        _fill(canvas, poly, COLLAR_BGR, (20, 20, 20), 1.0 * p.supersample)


def render(
    bar: BarModel,
    d1_mm: float,
    support_offset_mm: float,
    params: SimParams | None = None,
    rng: np.random.Generator | None = None,
) -> SimResult:
    """Rendert ein Bild einer Stange mit der Durchbiegung ``d1_mm``."""
    p = params or SimParams()
    rng = rng or np.random.default_rng(0)
    ss = p.supersample
    s = p.scale_px_per_mm * ss  # px pro mm auf der Superauflösungs-Leinwand
    width = int(round((bar.total_length_mm + 2 * p.margin_mm) * s))
    height = int(round(p.height_mm * s))
    ox = width / 2.0
    oy = p.origin_frac * height

    def to_px(x: float, y: float) -> tuple[float, float]:
        return ox + s * x, oy - s * y

    # Hintergrund mit leichtem Helligkeitsverlauf
    grad = np.linspace(215, 235, width, dtype=np.float32)[None, :]
    canvas = np.repeat(np.repeat(grad[:, :, None], height, axis=0), 3, axis=2).astype(np.uint8)

    # Stange: Schaft und Sleeves als Polylinien unterschiedlicher Dicke
    half = bar.total_length_mm / 2.0
    xs_mm = np.arange(-half, half + 1.0, 1.0)
    ys_mm = bend_profile(xs_mm, bar, support_offset_mm, d1_mm)
    pts = np.array([to_px(x, y) for x, y in zip(xs_mm, ys_mm, strict=True)])
    shaft_half = bar.shaft_length_mm / 2.0
    sleeve = np.abs(xs_mm) > shaft_half
    steel = (150, 148, 145)
    for mask, dia in ((~sleeve, bar.shaft_diameter_mm), (sleeve, SLEEVE_DIAMETER_MM)):
        for seg in np.split(pts[mask], np.where(np.diff(np.where(mask)[0]) > 1)[0] + 1):
            if len(seg) > 1:
                cv2.polylines(
                    canvas,
                    [np.round(seg).astype(np.int32)],
                    False,
                    steel,
                    thickness=max(int(round(dia * s)), 1),
                    lineType=cv2.LINE_AA,
                )

    # Scheiben und Klemmen auf den Sleeves (Scheiben stehen senkrecht zur Stangenachse)
    if p.plates_per_side > 0:
        _draw_plates(canvas, bar, xs_mm, ys_mm, p, to_px, s)

    # Mittenmarker: Klebeband (Rechteck um die Achse)
    cx, cy = to_px(0.0, float(ys_mm[len(ys_mm) // 2]))
    tw, th = TAPE_WIDTH_MM * s, (bar.shaft_diameter_mm + 4.0) * s
    _blend_rect(canvas, cx - tw / 2, cx + tw / 2, cy - th / 2, cy + th / 2, TAPE_BGR)

    # Gelbe Kugeln an den Sleeve-Enden (Mittelpunkt = Endpunkt, optional hängend)
    r_ball = p.ball_diameter_mm / 2.0 * s
    balls = {
        "left": to_px(-half, float(ys_mm[0]) - p.ball_hang_mm),
        "right": to_px(half, float(ys_mm[-1]) - p.ball_hang_mm),
    }
    for bx, by in balls.values():
        cv2.circle(
            canvas,
            (int(round(bx * 16)), int(round(by * 16))),
            int(round(r_ball * 16)),
            BALL_BGR,
            thickness=-1,
            lineType=cv2.LINE_AA,
            shift=4,
        )

    # ArUco-Referenzmarker im Hintergrund, mittig über der Stange
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    inner = int(round(p.aruco_size_mm * p.aruco_scale_ratio * s))
    border = int(round(MARKER_BORDER_MM * p.aruco_scale_ratio * s))
    img = cv2.aruco.generateImageMarker(dictionary, ARUCO_ID, inner)
    img = cv2.copyMakeBorder(img, border, border, border, border, cv2.BORDER_CONSTANT, value=255)
    ax, ay = to_px(0.0, p.aruco_offset_mm)
    _paste_marker(canvas, cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), ax, ay)

    points = {**balls, "centre": (cx, cy), "aruco": (ax, ay)}

    # Kamerarollen
    if p.roll_deg:
        m = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), p.roll_deg, 1.0)
        canvas = cv2.warpAffine(
            canvas, m, (width, height), flags=cv2.INTER_LINEAR, borderValue=(225, 225, 225)
        )
        points = {k: tuple(m @ np.array([x, y, 1.0])) for k, (x, y) in points.items()}

    # Herunterskalieren (Flächenmittelung => Subpixel-Antialiasing), Unschärfe, Rauschen
    out_w, out_h = width // ss, height // ss
    img = cv2.resize(canvas, (out_w, out_h), interpolation=cv2.INTER_AREA).astype(np.float32)
    # Pixelmitte-Konvention: Superauflösungs-Koordinate u -> (u + 0.5) / ss - 0.5
    points = {k: ((x + 0.5) / ss - 0.5, (y + 0.5) / ss - 0.5) for k, (x, y) in points.items()}
    if p.blur_sigma_px > 0:
        img = cv2.GaussianBlur(img, (0, 0), p.blur_sigma_px)
    img = img * p.brightness
    if p.noise_sigma > 0:
        img = img + rng.normal(0.0, p.noise_sigma, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return SimResult(img, d1_mm, p.scale_px_per_mm, points)


# --------------------------------------------------------------------------- Datensatz


def synthetic_d1_mm(
    bar: BarModel, load_kg: float, bar_factor: float, is_baseline: bool, rng: np.random.Generator
) -> float:
    """Plausibles, aber rein synthetisches Lastmodell: D1 ~ Last / d^4 (Balkentheorie)."""
    if is_baseline:
        return 0.0
    c0 = 0.0296  # mm/kg bei 29 mm; ergibt ca. 12 mm bei 425 kg
    eff = max(load_kg - bar.weight_kg, 0.0)
    length_factor = (bar.shaft_length_mm / 1310.0) ** 2
    d1 = c0 * eff * (29.0 / bar.shaft_diameter_mm) ** 4 * length_factor * bar_factor
    return float(d1 * (1.0 + rng.normal(0.0, 0.01)))


def plates_for_load(load_kg: float, bar_weight_kg: float = 20.0) -> int:
    """25-kg-Scheiben je Seite: 20 kg = leere Stange, sonst Last = 25 + 50 * n (inkl. Klemmen)."""
    if load_kg <= bar_weight_kg:
        return 0
    return int(round((load_kg - 25.0) / 50.0))


def generate_dataset(
    out_dir: Path,
    bars: BarCatalog,
    cfg: AnalysisConfig,
    params: SimParams | None = None,
    seed: int | None = None,
    roll_sd_deg: float = 0.3,
    only_bars: list[str] | None = None,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Schreibt Bilder, ``manifest.csv`` und ``truth.csv`` nach ``out_dir`` (gibt Truth zurück)."""
    from .manifest import expected_design, sha256_of

    out_dir = Path(out_dir)
    base = params or SimParams()
    seed = cfg.seed if seed is None else seed
    design = expected_design(bars, cfg)
    if only_bars:
        design = design[design["bar_id"].isin(only_bars)].reset_index(drop=True)
    bar_ids = bars.bar_ids()

    def one(i: int, row) -> dict:
        bar = bars.model_of(row.bar_id)
        ss = np.random.SeedSequence([seed, bar_ids.index(row.bar_id), i])
        rng = np.random.default_rng(ss)
        factor = 1.0 + 0.05 * np.random.default_rng([seed, bar_ids.index(row.bar_id)]).normal()
        d1 = synthetic_d1_mm(bar, row.load_kg, factor, row.is_baseline, rng)
        n_plates = 0 if row.is_baseline else plates_for_load(row.load_kg)
        p = SimParams(
            **{
                **base.__dict__,
                "roll_deg": float(rng.normal(0.0, roll_sd_deg)),
                "plates_per_side": n_plates,
            }
        )
        res = render(bar, d1, cfg.support_offset_mm, p, rng)
        tag = "baseline" if row.is_baseline else f"{row.load_kg:g}kg"
        rel = Path(row.bar_id) / f"run{row.run}_{tag}.jpg"
        (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / rel), res.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return {
            "bar_id": row.bar_id,
            "run": row.run,
            "load_kg": row.load_kg,
            "is_baseline": row.is_baseline,
            "image_path": rel.as_posix(),
            "image_sha256": sha256_of(out_dir / rel),
            "d1_true_mm": d1,
            "plates_per_side": n_plates,
            "scale_px_per_mm": res.scale_px_per_mm,
            "roll_deg": p.roll_deg,
        }

    rows = Parallel(n_jobs=n_jobs)(delayed(one)(i, r) for i, r in enumerate(design.itertuples()))
    truth = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth.to_csv(out_dir / "truth.csv", index=False)
    truth[["bar_id", "run", "load_kg", "is_baseline", "image_path", "image_sha256"]].to_csv(
        out_dir / "manifest.csv", index=False
    )
    return truth
