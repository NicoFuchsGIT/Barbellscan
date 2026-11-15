"""Vergleich der Auswertung gegen synthetische Ground Truth (V1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .manifest import KEY


def _stats(err: pd.Series, prefix: str) -> dict:
    sd = float(err.std(ddof=1)) if len(err) > 1 else float("nan")
    return {
        f"{prefix}_bias_mm": float(err.mean()),
        f"{prefix}_sd_mm": sd,
        f"{prefix}_rmse_mm": float(np.sqrt((err**2).mean())),
        f"{prefix}_loa_low_mm": float(err.mean() - 1.96 * sd),
        f"{prefix}_loa_high_mm": float(err.mean() + 1.96 * sd),
        f"{prefix}_max_abs_mm": float(err.abs().max()),
    }


def compare_to_truth(deflection: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Bias, Streuung, RMSE und 95-%-LoA von ΔD1 und D1 (mm) gegen die Ground Truth."""
    t = truth.astype({"cycle": str})[[*KEY, "d1_true_mm", "delta_d1_true_mm"]]
    df = deflection.astype({"cycle": str}).merge(t, on=KEY, how="inner")
    valid = df.dropna(subset=["delta_d1_mm"])
    out = {
        "n_images": int(len(df)),
        "n_valid": int(len(valid)),
        "detection_rate": float(len(valid) / len(df)) if len(df) else float("nan"),
    }
    out |= _stats(valid["delta_d1_mm"] - valid["delta_d1_true_mm"], "delta_d1")
    out |= _stats(valid["d1_mm"] - valid["d1_true_mm"], "d1")
    return out
