"""Statistik nach ANALYSIS_PLAN Abschnitt 6 (Eingang: ``cycle_summary.csv``).

- 6.1 H1: exakter einseitiger Permutationstest Deadlift vs. Power auf die Nachgiebigkeit c
  (Analyseeinheit = physische Stange), Mittelwertdifferenz und Hedges' g.
- 6.2 Deskriptiv: Kenngrößen je Stange mit 95-%-KI aus den Zyklen, Kategorie-Mittelwerte,
  Differenzen innerhalb eines Typs mit Welch-KI (ohne p-Werte).
- 6.3 H2: Linearität (ΔD_ring gegen das Lastmoment, Nachtrag N3), Restverformung (TOST gegen
  ±MDC95) und Hysterese, jeweils je Stange.
- 6.4 Reliabilität: ICC(1,1), SEM, MDC95 aus der einfaktoriellen Varianzanalyse.

Die Monte-Carlo-Fortpflanzung des Unsicherheitsbudgets (6.4) ist hier noch nicht enthalten;
sie braucht die Restverzeichnung aus der Plumb-Line-Prüfung an den echten Fotos.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats as st

from .config import AnalysisConfig, BarCatalog

# Vergleiche innerhalb eines Typs (Plan 6.2): (Bezeichnung, Stange a, Stange b), Differenz a − b
PAIRS = [
    ("Eleiko Training 2026 − 2016", "eleiko_training_2026", "eleiko_training_2016"),
    ("Eleiko Competition 2026 − 2016", "eleiko_comp_2026", "eleiko_comp_2016"),
]
BAR_QUANTITIES = [
    "compliance_mm_per_100kg",
    "delta_d1_peak_mm",
    "delta_dring_peak_mm",
    "residual_mm",
    "hysteresis_mm",
    "nonlin_ring_moment_mm",
    "nonlin_d1_moment_mm",
    "nonlin_at_peak_mm",
    "resid_sd_mm",
]
RELIABILITY_QUANTITIES = ["compliance_mm_per_100kg", "delta_d1_peak_mm", "delta_dring_peak_mm"]


def _clean(x) -> np.ndarray:
    x = np.asarray(x, float)
    return x[~np.isnan(x)]


def mean_ci(x, alpha: float = 0.05) -> dict:
    """Mittelwert, SD und t-Konfidenzintervall (NaN-Grenzen bei n < 2)."""
    x = _clean(x)
    n = len(x)
    mean = float(x.mean()) if n else np.nan
    sd = float(x.std(ddof=1)) if n > 1 else np.nan
    half = float(st.t.ppf(1 - alpha / 2, n - 1) * sd / np.sqrt(n)) if n > 1 else np.nan
    return {"n": n, "mean": mean, "sd": sd, "ci_low": mean - half, "ci_high": mean + half}


def hedges_g(a, b) -> float:
    """Standardisierte Mittelwertdifferenz a − b mit Kleinstichproben-Korrektur."""
    a, b = _clean(a), _clean(b)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    pooled = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if pooled == 0:
        return np.nan
    return float((a.mean() - b.mean()) / pooled * (1 - 3 / (4 * (na + nb) - 9)))


def permutation_test_greater(a, b) -> dict:
    """Exakter einseitiger Permutationstest auf mean(a) > mean(b) über alle Zuordnungen."""
    a, b = _clean(a), _clean(b)
    pooled = np.concatenate([a, b])
    n, na = len(pooled), len(a)
    if na == 0 or na == n:
        return {"mean_diff": np.nan, "p_exact": np.nan, "n_permutations": 0}
    observed = a.mean() - b.mean()
    total = pooled.sum()
    diffs = np.array(
        [
            (s := pooled[list(idx)].sum()) / na - (total - s) / (n - na)
            for idx in combinations(range(n), na)
        ]
    )
    # Toleranz gegen Rundungsfehler: Gleichstand zählt als mindestens so extrem
    extreme = int((diffs >= observed - 1e-12 * max(1.0, abs(observed))).sum())
    return {
        "mean_diff": float(observed),
        "p_exact": extreme / len(diffs),
        "n_permutations": len(diffs),
    }


def welch_diff(a, b, alpha: float = 0.05) -> dict:
    """Differenz mean(a) − mean(b) mit Welch-Konfidenzintervall."""
    a, b = _clean(a), _clean(b)
    out = {"n_a": len(a), "n_b": len(b), "diff": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    if len(a) < 2 or len(b) < 2:
        return out
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    diff, se = float(a.mean() - b.mean()), float(np.sqrt(va + vb))
    out["diff"] = diff
    if se > 0:
        dof = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
        half = float(st.t.ppf(1 - alpha / 2, dof) * se)
        out |= {"ci_low": diff - half, "ci_high": diff + half}
    return out


def tost_one_sample(x, bound: float, alpha: float = 0.05) -> dict:
    """Äquivalenztest: liegt der Mittelwert innerhalb ±bound? p = größerer der beiden p-Werte."""
    x = _clean(x)
    n = len(x)
    out = {"n": n, "mean": float(x.mean()) if n else np.nan, "p_tost": np.nan, "equivalent": False}
    if n < 2 or not np.isfinite(bound) or bound <= 0:
        return out
    se = x.std(ddof=1) / np.sqrt(n)
    if se == 0:
        p = 0.0 if abs(x.mean()) < bound else 1.0
    else:
        p_low = st.t.sf((x.mean() + bound) / se, n - 1)  # H0: Mittel <= -bound
        p_high = st.t.cdf((x.mean() - bound) / se, n - 1)  # H0: Mittel >= +bound
        p = float(max(p_low, p_high))
    out |= {"p_tost": p, "equivalent": bool(p < alpha)}
    return out


def icc_oneway(values: pd.Series, groups: pd.Series) -> dict:
    """ICC(1,1), SEM und MDC95 aus der einfaktoriellen ANOVA (Gruppen = Stangen).

    Bei ungleichen Gruppengrößen (fehlende Zyklen) wird die effektive Wiederholungszahl k0
    verwendet. Gruppen mit nur einem Wert tragen nichts zur Varianz innerhalb bei.
    """
    d = pd.DataFrame({"y": values, "g": groups}).dropna()
    sizes = d.groupby("g")["y"].size()
    n_groups, n_obs = len(sizes), len(d)
    out = {"n_bars": n_groups, "n_obs": n_obs}
    nan = {"icc_1_1": np.nan, "sem": np.nan, "mdc95": np.nan, "ms_between": np.nan}
    if n_groups < 2 or n_obs <= n_groups:
        return out | nan
    means = d.groupby("g")["y"].transform("mean")
    ms_within = float(((d["y"] - means) ** 2).sum() / (n_obs - n_groups))
    ms_between = float(((means - d["y"].mean()) ** 2).sum() / (n_groups - 1))
    k0 = (n_obs - (sizes**2).sum() / n_obs) / (n_groups - 1)
    denom = ms_between + (k0 - 1) * ms_within
    sem = float(np.sqrt(ms_within))
    return out | {
        "icc_1_1": float((ms_between - ms_within) / denom) if denom > 0 else np.nan,
        "sem": sem,
        "mdc95": float(1.96 * np.sqrt(2) * sem),
        "ms_between": ms_between,
    }


# --------------------------------------------------------------------------- Tabellen


def reliability_table(cycles: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"quantity": q} | icc_oneway(cycles[q], cycles["bar_id"])
        for q in RELIABILITY_QUANTITIES
        if q in cycles
    ]
    return pd.DataFrame(rows)


def bar_table(cycles: pd.DataFrame, bars: BarCatalog, alpha: float = 0.05) -> pd.DataFrame:
    """Je Stange: Mittel, SD und 95-%-KI über die Zyklen; Steifigkeit k = 100 / c."""
    rows = []
    for bar_id, g in cycles.groupby("bar_id", sort=False):
        r = {"bar_id": bar_id, "category": bars.bar(bar_id).category}
        for q in BAR_QUANTITIES:
            if q not in g:
                continue
            ci = mean_ci(g[q], alpha)
            if q == BAR_QUANTITIES[0]:
                r["n_cycles"] = ci["n"]
            r |= {f"{q}_{k}": v for k, v in ci.items() if k != "n"}
        c, lo, hi = (
            r.get(f"{BAR_QUANTITIES[0]}_{k}", np.nan) for k in ("mean", "ci_low", "ci_high")
        )
        r["stiffness_kg_per_mm"] = 100 / c if c else np.nan
        # Kehrwert dreht die Grenzen um; nur sinnvoll, solange das KI von c die 0 nicht enthält
        ok = np.isfinite([lo, hi]).all() and lo > 0
        r["stiffness_ci_low"] = 100 / hi if ok else np.nan
        r["stiffness_ci_high"] = 100 / lo if ok else np.nan
        rows.append(r)
    return pd.DataFrame(rows)


def category_table(per_bar: pd.DataFrame) -> pd.DataFrame:
    """Kategorie-Mittelwerte über die Stangenmittel."""
    cols = [f"{q}_mean" for q in RELIABILITY_QUANTITIES if f"{q}_mean" in per_bar]
    g = per_bar.groupby("category", sort=False)[cols]
    out = g.mean().join(g.std().add_suffix("_sd_between_bars"))
    out.insert(0, "n_bars", per_bar.groupby("category", sort=False).size())
    return out.reset_index()


def h1_table(per_bar: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    col = f"{BAR_QUANTITIES[0]}_mean"
    dead = per_bar.loc[per_bar["category"] == "deadlift", col]
    power = per_bar.loc[per_bar["category"] == "power", col]
    res = permutation_test_greater(dead, power)
    res |= {
        "n_deadlift": int(dead.notna().sum()),
        "n_power": int(power.notna().sum()),
        "mean_deadlift": float(dead.mean()),
        "mean_power": float(power.mean()),
        "hedges_g": hedges_g(dead, power),
        "alpha": alpha,
    }
    res["significant"] = bool(res["p_exact"] < alpha) if np.isfinite(res["p_exact"]) else False
    return pd.DataFrame([res])


def pair_table(cycles: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    rows = []
    for label, a, b in PAIRS:
        for q in RELIABILITY_QUANTITIES:
            if q in cycles:
                xa = cycles.loc[cycles["bar_id"] == a, q]
                xb = cycles.loc[cycles["bar_id"] == b, q]
                rows.append({"comparison": label, "quantity": q} | welch_diff(xa, xb, alpha))
    return pd.DataFrame(rows)


def h2_table(cycles: pd.DataFrame, reliability: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """H2 je Stange gegen MDC95 (Plan 6.3, Linearität nach Nachtrag N3)."""
    mdc = reliability.set_index("quantity")["mdc95"] if len(reliability) else pd.Series(dtype=float)
    mdc_d1 = float(mdc.get("delta_d1_peak_mm", np.nan))
    mdc_ring = float(mdc.get("delta_dring_peak_mm", np.nan))
    rows = []
    for bar_id, g in cycles.groupby("bar_id", sort=False):
        r = {"bar_id": bar_id, "mdc95_d1_mm": mdc_d1, "mdc95_dring_mm": mdc_ring}
        if "nonlin_ring_moment_mm" in g:
            nl = mean_ci(g["nonlin_ring_moment_mm"], alpha)
            r["nonlin_ring_moment_mm"] = nl["mean"]
            r["linear_within_mdc95"] = (
                bool(abs(nl["mean"]) <= mdc_ring)
                if np.isfinite([nl["mean"], mdc_ring]).all()
                else None
            )
        t = tost_one_sample(g["residual_mm"], mdc_d1, alpha)
        r |= {
            "residual_mm": t["mean"],
            "residual_p_tost": t["p_tost"],
            "residual_equivalent_to_zero": t["equivalent"],
        }
        hy = mean_ci(g["hysteresis_mm"], alpha)
        r |= {
            "hysteresis_mm": hy["mean"],
            "hysteresis_ci_low": hy["ci_low"],
            "hysteresis_ci_high": hy["ci_high"],
            "hysteresis_within_mdc95": (
                bool(abs(hy["mean"]) <= mdc_d1) if np.isfinite([hy["mean"], mdc_d1]).all() else None
            ),
        }
        rows.append(r)
    return pd.DataFrame(rows)


def run_all(cycles: pd.DataFrame, bars: BarCatalog, cfg: AnalysisConfig) -> dict[str, pd.DataFrame]:
    """Alle Tabellen nach Plan 6: ``bars, categories, h1, pairs, reliability, h2``."""
    alpha = cfg.alpha
    per_bar = bar_table(cycles, bars, alpha)
    reliability = reliability_table(cycles)
    return {
        "bars": per_bar,
        "categories": category_table(per_bar),
        "h1": h1_table(per_bar, alpha),
        "pairs": pair_table(cycles, alpha),
        "reliability": reliability,
        "h2": h2_table(cycles, reliability, alpha),
    }
