"""Synthetische Frontansicht-Bilder mit exakt bekannter Durchbiegung (FR-15, Validierung V1).

Weltkoordinaten in mm: x entlang der Stange (Ursprung = Mitte), y nach oben, y = 0 auf der
Auflagelinie. Zwischen den Auflagern wölbt sich der Schaft nach oben, die Enden hängen herab;
die Sleeves (starr) bleiben gerade. Marker wie beim echten Shooting (ANALYSIS_PLAN Abschnitt 3):
gelbe Kugeln 35 mm hinter den Sleeve-Stirnflächen, gelbe Bänder an Mitte und Ringmarkierungen,
gelbe Monolift-Knöpfe als Störobjekte oberhalb der Stange.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml
from joblib import Parallel, delayed

from .config import AnalysisConfig, Bar, BarCatalog, Geometry

YELLOW_BGR = (20, 210, 245)
STEEL_BGR = (150, 148, 145)
PLATE_BGR = (35, 35, 190)  # rote 25-kg-Scheibe
PLATE_EDGE_BGR = (15, 15, 90)
COLLAR_BGR = (60, 60, 60)
CAP_BGR = (25, 25, 25)
SLEEVE_DIAMETER_MM = 50.0
KNOB_X_MM, KNOB_Y_MM, KNOB_D_MM = 350.0, 230.0, 40.0  # wie im Shooting ca. 700 mm Abstand


@dataclass
class SimParams:
    scale_px_per_mm: float = 1.0
    supersample: int = 4
    blur_sigma_px: float = 0.8
    noise_sigma: float = 2.0
    roll_deg: float = 0.0
    shift_px: tuple[float, float] = (0.0, 0.0)  # Kameraversatz
    brightness: float = 1.0
    background: int = 45  # dunkle Holzwand
    height_mm: float = 640.0
    margin_mm: float = 60.0
    origin_frac: float = 0.45  # Lage der Auflagelinie von oben
    plates_per_side: int = 0
    plate_thickness_mm: float = 27.0
    plate_diameter_mm: float = 450.0
    collar_width_mm: float = 30.0
    collar_height_mm: float = 90.0
    distractors: bool = True  # gelbe Monolift-Knöpfe


@dataclass
class SimResult:
    image: np.ndarray
    d1_mm: float
    dring_mm: float
    scale_px_per_mm: float
    points_px: dict[str, tuple[float, float]] = field(default_factory=dict)


def bend_profile(
    x_mm: np.ndarray, bar: Bar, support_offset_mm: float, d1_mm: float, end_x_mm: float
) -> np.ndarray:
    """Höhe y(x) der Stangenachse, normiert auf D1 = y(0) - y(end_x).

    Krümmung konstant zwischen den Auflagern, danach linear auf 0 am Schaftende abfallend,
    Sleeves und Kappen starr (gerade). ``end_x_mm`` ist die x-Lage der Endmarker.
    """
    a = support_offset_mm
    xs = bar.shaft_length_mm / 2.0
    dx = 0.25
    grid = np.arange(0.0, max(end_x_mm, np.max(np.abs(x_mm))) + dx, dx)
    kappa = np.where(
        grid <= a, 1.0, np.where(grid <= xs, 1.0 - (grid - a) / max(xs - a, 1e-9), 0.0)
    )
    theta = np.concatenate([[0.0], np.cumsum((kappa[1:] + kappa[:-1]) / 2 * dx)])
    y = -np.concatenate([[0.0], np.cumsum((theta[1:] + theta[:-1]) / 2 * dx)])  # Mitte oben
    y -= np.interp(a, grid, y)  # y(Auflager) = 0
    unit = y[0] - np.interp(end_x_mm, grid, y)
    scale = d1_mm / unit if unit else 0.0
    return np.interp(np.abs(x_mm), grid, y * scale)


def _rect_on_axis(xs_mm, ys_mm, x_c, width_mm, height_mm, to_px) -> np.ndarray:
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


def _fill(canvas, poly, fill, edge=None, edge_px=1) -> None:
    sub = np.round(np.asarray(poly) * 16).astype(np.int32)
    cv2.fillPoly(canvas, [sub], fill, lineType=cv2.LINE_AA, shift=4)
    if edge is not None:
        cv2.polylines(canvas, [sub], True, edge, max(int(edge_px), 1), cv2.LINE_AA, shift=4)


def _circle(canvas, cx, cy, r, bgr) -> None:
    c = (int(round(cx * 16)), int(round(cy * 16)))
    cv2.circle(canvas, c, int(round(r * 16)), bgr, -1, cv2.LINE_AA, shift=4)


def render(
    bar: Bar,
    d1_mm: float,
    geometry: Geometry | None = None,
    params: SimParams | None = None,
    rng: np.random.Generator | None = None,
) -> SimResult:
    """Rendert ein Bild einer Stange mit der Durchbiegung ``d1_mm`` (Mitte zur Kugel-Sehne)."""
    g = geometry or Geometry()
    p = params or SimParams()
    rng = rng or np.random.default_rng(0)
    ss = p.supersample
    s = p.scale_px_per_mm * ss
    half = bar.total_length_mm / 2.0
    end_x = half + g.ball_offset_mm
    # Leinwand als Vielfaches von ss, damit das Herunterskalieren exakt um den Faktor ss erfolgt
    width = ss * int(round((2 * end_x + g.ball_diameter_mm + 2 * p.margin_mm) * s / ss))
    height = ss * int(round(p.height_mm * s / ss))
    ox = width / 2.0 + p.shift_px[0] * ss
    oy = p.origin_frac * height + p.shift_px[1] * ss

    def to_px(x: float, y: float) -> tuple[float, float]:
        return ox + s * x, oy - s * y

    grad = np.linspace(p.background - 8, p.background + 8, width, dtype=np.float32)[None, :]
    canvas = np.repeat(np.repeat(grad[:, :, None], height, axis=0), 3, axis=2).astype(np.uint8)

    xs_mm = np.arange(-end_x, end_x + 0.5, 0.5)
    ys_mm = bend_profile(xs_mm, bar, g.support_offset_loaded_mm, d1_mm, end_x)
    pts = np.array([to_px(x, y) for x, y in zip(xs_mm, ys_mm, strict=True)])

    # Stange: Schaft, Sleeves, Kappen
    shaft_half = bar.shaft_length_mm / 2.0
    ax = np.abs(xs_mm)
    parts = (
        (ax <= shaft_half, bar.shaft_diameter_mm, STEEL_BGR),
        ((ax > shaft_half) & (ax <= half), SLEEVE_DIAMETER_MM, STEEL_BGR),
        ((ax > half) & (ax <= end_x - g.ball_diameter_mm / 2), 55.0, CAP_BGR),
    )
    for mask, dia, col in parts:
        for seg in np.split(pts[mask], np.where(np.diff(np.where(mask)[0]) > 1)[0] + 1):
            if len(seg) > 1:
                cv2.polylines(
                    canvas,
                    [np.round(seg).astype(np.int32)],
                    False,
                    col,
                    max(int(round(dia * s)), 1),
                    cv2.LINE_AA,
                )

    # Scheiben und Klemmen (senkrecht zur Stangenachse), innen am Sleeve-Anschlag
    x0 = shaft_half + 5.0
    t = p.plate_thickness_mm
    if p.plates_per_side > 0:
        for sign in (-1.0, 1.0):
            for k in range(p.plates_per_side):
                xc = sign * (x0 + (k + 0.5) * t)
                poly = _rect_on_axis(xs_mm, ys_mm, xc, t, p.plate_diameter_mm, to_px)
                _fill(canvas, poly, PLATE_BGR, PLATE_EDGE_BGR, ss)
            xc = sign * (x0 + p.plates_per_side * t + p.collar_width_mm / 2)
            poly = _rect_on_axis(xs_mm, ys_mm, xc, p.collar_width_mm, p.collar_height_mm, to_px)
            _fill(canvas, poly, COLLAR_BGR)

    # Gelbe Bänder: Mitte und Ringmarkierungen (umlaufend, etwas dicker als der Schaft)
    tape_h = bar.shaft_diameter_mm + 1.0
    tapes = {
        "centre": 0.0,
        "ring_left": -bar.ring_spacing_mm / 2,
        "ring_right": bar.ring_spacing_mm / 2,
    }
    points = {}
    for name, xt in tapes.items():
        _fill(canvas, _rect_on_axis(xs_mm, ys_mm, xt, g.tape_width_mm, tape_h, to_px), YELLOW_BGR)
        points[name] = to_px(xt, float(np.interp(xt, xs_mm, ys_mm)))

    # Kugeln auf der Achse, 35 mm hinter der Sleeve-Stirn
    r_ball = g.ball_diameter_mm / 2.0 * s
    for name, xb in (("left", -end_x), ("right", end_x)):
        points[name] = to_px(xb, float(np.interp(xb, xs_mm, ys_mm)))
        _circle(canvas, *points[name], r_ball, YELLOW_BGR)

    # Störobjekte: gelbe Monolift-Knöpfe oberhalb der Stange
    if p.distractors:
        for sign in (-1.0, 1.0):
            _circle(canvas, *to_px(sign * KNOB_X_MM, KNOB_Y_MM), KNOB_D_MM / 2 * s, YELLOW_BGR)

    if p.roll_deg:
        m = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), p.roll_deg, 1.0)
        canvas = cv2.warpAffine(
            canvas,
            m,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderValue=(p.background,) * 3,
        )
        points = {k: tuple(m @ np.array([x, y, 1.0])) for k, (x, y) in points.items()}

    out_w, out_h = width // ss, height // ss
    img = cv2.resize(canvas, (out_w, out_h), interpolation=cv2.INTER_AREA).astype(np.float32)
    points = {k: ((x + 0.5) / ss - 0.5, (y + 0.5) / ss - 0.5) for k, (x, y) in points.items()}
    if p.blur_sigma_px > 0:
        img = cv2.GaussianBlur(img, (0, 0), p.blur_sigma_px)
    img = img * p.brightness
    if p.noise_sigma > 0:
        img = img + rng.normal(0.0, p.noise_sigma, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)

    y0 = float(np.interp(0.0, xs_mm, ys_mm))
    dring = y0 - float(np.interp(bar.ring_spacing_mm / 2, xs_mm, ys_mm))
    return SimResult(img, d1_mm, dring, p.scale_px_per_mm, points)


# --------------------------------------------------------------------------- Datensatz


def synthetic_compliance_mm_per_kg(bar: Bar, bar_factor: float = 1.0) -> float:
    """Rein synthetisches Lastmodell: Nachgiebigkeit ~ Schaftlänge^2 / d^4 (Balkentheorie).

    Größenordnung wie im Shooting: Power ca. 70 mm, Deadlift ca. 105 mm bei 405 kg.
    """
    c0 = 0.17  # mm/kg bei 29 mm Schaft und 1310 mm Schaftlänge
    return (
        c0 * (29.0 / bar.shaft_diameter_mm) ** 4 * (bar.shaft_length_mm / 1310.0) ** 2 * bar_factor
    )


def generate_dataset(
    out_dir: Path,
    bars: BarCatalog,
    cfg: AnalysisConfig,
    params: SimParams | None = None,
    seed: int | None = None,
    roll_sd_deg: float = 0.3,
    shift_sd_px: float = 3.0,
    prebend_sd_mm: float = 2.0,
    only_bars: list[str] | None = None,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """Schreibt Bilder, ``manifest.csv``, ``truth.csv`` und ``analysis.yaml`` nach ``out_dir``.

    ``analysis.yaml`` ist die übergebene Config mit Detektionsparametern für die Synthetik
    (nominaler Maßstab = Simulationsmaßstab, keine ROI).
    """
    from .manifest import COLUMNS, expected_design, sha256_of

    out_dir = Path(out_dir)
    base = params or SimParams()
    seed = cfg.seed if seed is None else seed
    design = expected_design(bars, cfg)
    if only_bars:
        design = design[design["bar_id"].isin(only_bars)].reset_index(drop=True)
    bar_ids = bars.bar_ids()

    def one(i: int, row) -> dict:
        bar = bars.bar(row.bar_id)
        b = bar_ids.index(row.bar_id)
        c = cfg.cycles.index(row.cycle)
        rng = np.random.default_rng(np.random.SeedSequence([seed, b, c, int(row.step)]))
        factor = 1.0 + 0.05 * np.random.default_rng([seed, b]).normal()
        d0 = prebend_sd_mm * np.random.default_rng([seed, b, c, 999]).normal()
        delta = synthetic_compliance_mm_per_kg(bar, factor) * row.added_mass_kg
        p = replace(
            base,
            roll_deg=float(rng.normal(0.0, roll_sd_deg)),
            shift_px=(float(rng.normal(0, shift_sd_px)), float(rng.normal(0, shift_sd_px))),
            plates_per_side=int(row.plates_per_side),
        )
        res = render(bar, d0 + delta, cfg.geometry, p, rng)
        rel = Path(row.bar_id) / f"{row.cycle}_{int(row.step):02d}.jpg"
        (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / rel), res.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return {
            **{k: getattr(row, k) for k in COLUMNS[:6]},
            "image_path": rel.as_posix(),
            "image_sha256": sha256_of(out_dir / rel),
            "d1_true_mm": d0 + delta,
            "delta_d1_true_mm": delta,
            "dring_true_mm": res.dring_mm,
            "scale_px_per_mm": res.scale_px_per_mm,
            "roll_deg": p.roll_deg,
        }

    rows = Parallel(n_jobs=n_jobs)(delayed(one)(i, r) for i, r in enumerate(design.itertuples()))
    truth = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth.to_csv(out_dir / "truth.csv", index=False)
    truth[COLUMNS].to_csv(out_dir / "manifest.csv", index=False)
    sim_cfg = cfg.model_copy(
        update={
            "detection": cfg.detection.model_copy(
                update={"nominal_px_per_mm": base.scale_px_per_mm, "roi_frac": None}
            )
        }
    )
    with (out_dir / "analysis.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(sim_cfg.model_dump(mode="json"), f, sort_keys=False, allow_unicode=True)
    return truth
