"""Vergleich Tracking gegen synthetische Ground Truth (V1)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compare_to_truth(tracking: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Bias, Streuung, RMSE und 95-%-Limits of Agreement von D1 (mm) gegen ``d1_true_mm``."""
    key = ["bar_id", "run", "load_kg", "is_baseline"]
    df = tracking.merge(truth[key + ["d1_true_mm"]], on=key, how="inner")
    valid = df.dropna(subset=["d1_mm"])
    err = valid["d1_mm"] - valid["d1_true_mm"]
    sd = float(err.std(ddof=1)) if len(err) > 1 else float("nan")
    return {
        "n_images": int(len(df)),
        "n_valid": int(len(valid)),
        "detection_rate": float(len(valid) / len(df)) if len(df) else float("nan"),
        "bias_mm": float(err.mean()),
        "sd_mm": sd,
        "rmse_mm": float(np.sqrt((err**2).mean())),
        "loa_low_mm": float(err.mean() - 1.96 * sd),
        "loa_high_mm": float(err.mean() + 1.96 * sd),
        "max_abs_error_mm": float(err.abs().max()),
    }
