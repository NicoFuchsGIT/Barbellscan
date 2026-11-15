"""Durchbiegung aus Markerpunkten (ANALYSIS_PLAN Abschnitt 5).

- ``D1``: senkrechter Abstand des Mittenbands zur Sehne durch die Kugeln (positiv = Enden unten).
- ``ΔD1``: D1 minus D1 bei Stufe 0 desselben Zyklus.
- ``D_ring`` / ``ΔD_ring``: wie oben, aber mit der Sehne durch die beiden Ringbänder.
- Skala je Zyklus: Ringabstand in px (Mittel aus Stufe 0 und letzter Stufe) / Ringabstand in mm.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AnalysisConfig, BarCatalog


def chord_offset_px(
    left: tuple[float, float], right: tuple[float, float], centre: tuple[float, float]
) -> float:
    """Abstand der Mitte zur Sehne links-rechts, senkrecht zur Sehne (rollinvariant).

    Positiv, wenn die Sehne unter der Mitte liegt (Bildkoordinaten: y nach unten).
    """
    left, right, centre = (np.asarray(p, float) for p in (left, right, centre))
    u = right - left
    u = u / np.linalg.norm(u)
    n = np.array([-u[1], u[0]])  # zeigt bei u = (1, 0) nach unten (+y)
    return float(n @ (left - centre))


def d1_mm(left, right, centre, scale_px_per_mm: float) -> float:
    return chord_offset_px(left, right, centre) / scale_px_per_mm


def _append_flag(flags: pd.Series, mask: pd.Series, flag: str) -> pd.Series:
    add = np.where(mask, flag, "")
    return pd.Series(
        [";".join(x for x in (a, b) if x) for a, b in zip(flags, add, strict=True)],
        index=flags.index,
    )


def add_deflection(tracking: pd.DataFrame, bars: BarCatalog, cfg: AnalysisConfig) -> pd.DataFrame:
    """Ergänzt Skala (je Zyklus), D1, ΔD1, D_ring, ΔD_ring in mm und die Kugel-Gegenprobe."""
    df = tracking.copy()
    df["cycle"] = df["cycle"].astype(str)
    key = ["bar_id", "cycle"]
    baseline_steps = [0, cfg.final_step]
    ref = df[df["step"].isin(baseline_steps)]
    scale = ref.groupby(key).agg(ring_px=("ring_dist_px", "mean"), ball_px=("ball_dist_px", "mean"))
    scale = scale.reset_index()
    spacing = scale["bar_id"].map(lambda b: bars.bar(b).ring_spacing_mm)
    span = scale["bar_id"].map(lambda b: bars.bar(b).ball_span_mm(cfg.geometry.ball_offset_mm))
    scale["px_per_mm"] = scale["ring_px"] / spacing
    scale["px_per_mm_ball"] = scale["ball_px"] / span
    # Aus der Ring-Skala abgeleitete Stangenlänge (Gegenprobe zu bars.yaml, Plan Abschnitt 9)
    scale["implied_length_mm"] = (
        scale["ball_px"] / scale["px_per_mm"] - 2 * cfg.geometry.ball_offset_mm
    )
    df = df.merge(scale.drop(columns=["ring_px", "ball_px"]), on=key, how="left")

    # Primär: Bänder auf der Schaftachse; "_centroid": Schwerpunkt der Bandfläche (Sensitivität)
    px_cols = {
        "d1": "d1_px",
        "dring": "dring_px",
        "d1_centroid": "d1_px_centroid",
        "dring_centroid": "dring_px_centroid",
    }
    quantities = list(px_cols)
    for q, col in px_cols.items():
        df[f"{q}_mm"] = df[col] / df["px_per_mm"] if col in df else np.nan
    base = df[df["step"] == 0].set_index(key)[[f"{q}_mm" for q in quantities]]
    base.columns = [f"{q}_base_mm" for q in quantities]
    df = df.join(base, on=key)
    for q in quantities:
        df[f"delta_{q}_mm"] = df[f"{q}_mm"] - df[f"{q}_base_mm"]

    flags = df.get("detect_flags", pd.Series("", index=df.index)).fillna("").astype(str)
    flags = _append_flag(flags, df["px_per_mm"].isna(), "no_scale")
    flags = _append_flag(flags, df["d1_base_mm"].isna(), "no_baseline")
    df["deflection_flags"] = flags
    return df.drop(columns=list(base.columns))


def _ols(x: np.ndarray, y: np.ndarray, degree: int):
    """Polynom-Fit; gibt Koeffizienten (höchster Grad zuerst) und Residuen-SD zurück."""
    coef = np.polyfit(x, y, degree)
    resid = y - np.polyval(coef, x)
    dof = len(x) - (degree + 1)
    sd = float(np.sqrt((resid**2).sum() / dof)) if dof > 0 else np.nan
    return coef, sd


def cycle_summary(df: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    """Kenngrößen je Stange und Zyklus (Plan 5 und 6.3)."""
    peak, final = cfg.peak_step, cfg.final_step
    rows = []
    for (bar_id, cycle), g in df.groupby(["bar_id", "cycle"], sort=False):
        up = g[(g["phase"] == "up")].dropna(subset=["delta_d1_mm"])
        down = g[(g["phase"] == "down") & (g["step"] != final)].dropna(subset=["delta_d1_mm"])
        r = {"bar_id": bar_id, "cycle": cycle, "n_up": len(up)}
        for col in ("px_per_mm", "px_per_mm_ball", "implied_length_mm"):
            r[col] = g[col].iloc[0] if col in g else np.nan
        x, y = up["added_mass_kg"].to_numpy(float), up["delta_d1_mm"].to_numpy(float)
        if len(up) >= 3:
            (b1, b0), resid_sd = _ols(x, y, 1)
            r["slope_mm_per_kg"] = b1
            r["intercept_mm"] = b0
            r["compliance_mm_per_100kg"] = 100 * b1
            r["stiffness_kg_per_mm"] = 1 / b1 if b1 else np.nan
            r["r2"] = 1 - (resid_sd**2 * (len(x) - 2)) / (((y - y.mean()) ** 2).sum() or np.nan)
            r["resid_sd_mm"] = resid_sd
        if len(up) >= 4:
            q, _ = _ols(x, y, 2)
            m = x.max()
            r["nonlin_at_peak_mm"] = float(np.polyval(q, m) - (b1 * m + b0))
        at = g.set_index("step")["delta_d1_mm"]
        r["delta_d1_peak_mm"] = at.get(peak, np.nan)
        r["residual_mm"] = at.get(final, np.nan)
        r["delta_dring_peak_mm"] = g.set_index("step")["delta_dring_mm"].get(peak, np.nan)
        pairs = up.merge(down, on="added_mass_kg", suffixes=("_up", "_down"))
        pairs = pairs[pairs["added_mass_kg"] > 0]
        r["hysteresis_mm"] = (
            float((pairs["delta_d1_mm_down"] - pairs["delta_d1_mm_up"]).mean())
            if len(pairs)
            else np.nan
        )
        r["n_hysteresis_pairs"] = len(pairs)
        upc = up.dropna(subset=["delta_d1_centroid_mm"])
        if len(upc) >= 3:
            b1c, _ = np.polyfit(upc["added_mass_kg"], upc["delta_d1_centroid_mm"], 1)
            r["compliance_centroid_mm_per_100kg"] = 100 * b1c
        rows.append(r)
    return pd.DataFrame(rows)


def bar_summary(cycles: pd.DataFrame, bars: BarCatalog) -> pd.DataFrame:
    """Je Stange: Mittel über Zyklen (Analyseeinheit = physische Stange, Plan 5)."""
    cols = [
        "compliance_mm_per_100kg",
        "delta_d1_peak_mm",
        "delta_dring_peak_mm",
        "residual_mm",
        "hysteresis_mm",
        "nonlin_at_peak_mm",
        "implied_length_mm",
        "compliance_centroid_mm_per_100kg",
    ]
    cols = [c for c in cols if c in cycles]
    g = cycles.groupby("bar_id", sort=False)[cols]
    out = g.mean().add_suffix("_mean").join(g.std().add_suffix("_sd")).join(g.count().iloc[:, :1])
    out = out.rename(columns={f"{cols[0]}": "n_cycles"}).reset_index()
    out["stiffness_kg_per_mm"] = 100 / out["compliance_mm_per_100kg_mean"]
    out.insert(1, "category", out["bar_id"].map(lambda b: bars.bar(b).category))
    out.insert(2, "nominal_length_mm", out["bar_id"].map(lambda b: bars.bar(b).total_length_mm))
    return out
