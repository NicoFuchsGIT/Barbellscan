"""Abbildungen aus den Tabellen von ``deflect`` und ``stats`` (englisch beschriftet)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from .config import BarCatalog  # noqa: E402

# Farbe und Markerform je Kategorie; drei Farbtöne, die auch bei Farbfehlsichtigkeit trennbar sind,
# die einzelne Gewichtheberstange neutral. Die Form trägt die Kategorie zusätzlich.
CATEGORY_STYLE = {
    "power": ("#2a78d6", "o", "Power bar"),
    "deadlift": ("#eb6834", "s", "Deadlift bar"),
    "squat": ("#1baf7a", "^", "Squat bar"),
    "weightlifting": ("#55554f", "D", "Weightlifting bar"),
}
FALLBACK_STYLE = ("#55554f", "o", "Other")
INK, MUTED, GRID = "#1f1f1d", "#6b6a63", "#e4e3dc"

RC = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "text.color": INK,
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "legend.frameon": False,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
}


def bar_label(bar_id: str) -> str:
    """``eleiko_comp_2016`` -> ``Eleiko Comp 2016``, ``zkc_iwf`` -> ``ZKC IWF``."""
    parts = bar_id.split("_")
    return " ".join(p.upper() if len(p) <= 3 and p.isalpha() else p.title() for p in parts)


def _style(category: str) -> tuple[str, str, str]:
    return CATEGORY_STYLE.get(category, FALLBACK_STYLE)


def _bar_order(cycles: pd.DataFrame, categories: dict[str, str]) -> list[str]:
    """Stangen nach Kategorie (Reihenfolge der Legende), darin nach Nachgiebigkeit."""
    c = cycles.groupby("bar_id")["compliance_mm_per_100kg"].mean()
    rank = {cat: i for i, cat in enumerate(CATEGORY_STYLE)}
    return sorted(c.index, key=lambda b: (rank.get(categories.get(b, ""), 99), c[b]))


def _category_legend(fig_or_ax, categories: list[str], **kwargs) -> None:
    handles = [
        Line2D([], [], color=_style(c)[0], marker=_style(c)[1], linestyle="", markersize=6)
        for c in categories
    ]
    fig_or_ax.legend(handles, [_style(c)[2] for c in categories], **kwargs)


def _present(order: list[str], categories: dict[str, str]) -> list[str]:
    seen = {categories.get(b, "") for b in order}
    return [c for c in CATEGORY_STYLE if c in seen]


def _save(fig, out_dir: Path, name: str, formats: tuple[str, ...]) -> list[Path]:
    paths = []
    for fmt in formats:
        path = out_dir / f"{name}.{fmt}"
        fig.savefig(path)
        paths.append(path)
    plt.close(fig)
    return paths


def _grid(n: int, ncols: int = 5, panel=(2.5, 2.1)):
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(ncols * panel[0], nrows * panel[1]),
        sharex=True,
        sharey=True,
        squeeze=False,
        layout="constrained",
    )
    flat = list(axes.ravel())
    for ax in flat[n:]:
        ax.set_visible(False)
    return fig, flat[:n], axes


def plot_curve_grid(
    deflection: pd.DataFrame,
    cycles: pd.DataFrame,
    categories: dict[str, str],
    *,
    x: str,
    y: str,
    xlabel: str,
    ylabel: str,
    title: str,
    fit_line: bool,
):
    """Eine Kachel je Stange: Belastung gefüllt, Entlastung hohl, alle Zyklen übereinander."""
    order = _bar_order(cycles, categories)
    fig, axes, grid = _grid(len(order))
    cyc_mean = cycles.groupby("bar_id")[
        ["slope_mm_per_kg", "intercept_mm", "compliance_mm_per_100kg"]
    ].mean()
    for ax, bar_id in zip(axes, order, strict=True):
        colour, marker, _ = _style(categories.get(bar_id, ""))
        d = deflection[deflection["bar_id"] == bar_id].dropna(subset=[x, y])
        up, down = d[d["phase"] == "up"], d[d["phase"] != "up"]
        if fit_line:
            xs = np.array([0.0, up[x].max()])
            row = cyc_mean.loc[bar_id]
            ax.plot(xs, row["intercept_mm"] + row["slope_mm_per_kg"] * xs, color=MUTED, lw=1)
        ax.plot(down[x], down[y], marker, mfc="white", mec=colour, mew=0.9, ms=4.5, ls="")
        ax.plot(up[x], up[y], marker, color=colour, mec="white", mew=0.5, ms=4.5, ls="")
        c = cyc_mean.loc[bar_id, "compliance_mm_per_100kg"]
        ax.set_title(f"{bar_label(bar_id)}\nc = {c:.1f} mm/100 kg", loc="left")
    for ax in grid[-1]:
        ax.set_xlabel(xlabel)
    for ax in axes:
        ax.tick_params(labelbottom=True)
    for row in grid:
        row[0].set_ylabel(ylabel)
    handles = [
        Line2D([], [], color=INK, marker="o", ls="", ms=5, mec="white"),
        Line2D([], [], color=INK, marker="o", ls="", ms=5, mfc="white"),
    ]
    labels = ["Loading", "Unloading"]
    if fit_line:
        handles.append(Line2D([], [], color=MUTED, lw=1))
        labels.append("OLS fit (loading)")
    present = _present(order, categories)
    handles += [
        Line2D([], [], color=_style(c)[0], marker=_style(c)[1], ls="", ms=6) for c in present
    ]
    labels += [_style(c)[2] for c in present]
    fig.legend(handles, labels, loc="outside lower center", ncols=len(labels))
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold")
    return fig


def _spread_labels(values: np.ndarray, min_gap: float) -> np.ndarray:
    """Beschriftungspositionen so verschieben, dass sie sich nicht überdecken."""
    idx = np.argsort(values)
    pos = values[idx].astype(float).copy()
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + min_gap)
    pos -= max(0.0, (pos - values[idx]).mean())  # Verschiebung mitteln statt nur nach oben
    for i in range(1, len(pos)):
        pos[i] = max(pos[i], pos[i - 1] + min_gap)
    out = np.empty_like(pos)
    out[idx] = pos
    return out


def plot_overview(deflection: pd.DataFrame, cycles: pd.DataFrame, categories: dict[str, str]):
    """Alle Stangen in einem Bild: mittlere Belastungskurve, Farbe nach Kategorie."""
    order = _bar_order(cycles, categories)
    up = deflection[deflection["phase"] == "up"].dropna(subset=["delta_d1_mm"])
    mean = up.groupby(["bar_id", "added_mass_kg"])["delta_d1_mm"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(8, 5.4), layout="constrained")
    ends = {}
    for bar_id in order:
        colour, marker, _ = _style(categories.get(bar_id, ""))
        d = mean[mean["bar_id"] == bar_id].sort_values("added_mass_kg")
        ax.plot(
            d["added_mass_kg"], d["delta_d1_mm"], color=colour, lw=1.6,
            marker=marker, ms=4.5, mec="white", mew=0.6,
        )  # fmt: skip
        ends[bar_id] = (d["added_mass_kg"].iloc[-1], d["delta_d1_mm"].iloc[-1])
    y_end = np.array([ends[b][1] for b in order])
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    y_lab = _spread_labels(y_end, span * 0.034)
    x_max = max(v[0] for v in ends.values())
    for bar_id, y0, y1 in zip(order, y_end, y_lab, strict=True):
        ax.plot([x_max + 4, x_max + 14], [y0, y1], color=GRID, lw=0.8, clip_on=False)
        ax.text(x_max + 16, y1, bar_label(bar_id), va="center", fontsize=8, color=INK)
    ax.set_xlim(-8, x_max * 1.32)
    ax.set_xticks(sorted(mean["added_mass_kg"].unique())[::2])
    ax.set_xlabel("Added mass (kg)")
    ax.set_ylabel("Centre deflection ΔD1 (mm)")
    ax.set_title(
        "Deflection under load, mean of loading phases", loc="left", fontsize=11, fontweight="bold"
    )
    _category_legend(ax, _present(order, categories), loc="upper left")
    return fig


def plot_compliance(cycles: pd.DataFrame, bars: pd.DataFrame, categories: dict[str, str]):
    """Nachgiebigkeit je Stange: Mittel mit 95-%-KI, die drei Zyklen als kleine Punkte."""
    b = bars.set_index("bar_id").sort_values("compliance_mm_per_100kg_mean")
    fig, ax = plt.subplots(figsize=(7.5, 0.36 * len(b) + 1.4), layout="constrained")
    for i, (bar_id, row) in enumerate(b.iterrows()):
        colour, marker, _ = _style(categories.get(bar_id, ""))
        mean = row["compliance_mm_per_100kg_mean"]
        lo, hi = row["compliance_mm_per_100kg_ci_low"], row["compliance_mm_per_100kg_ci_high"]
        pts = cycles.loc[cycles["bar_id"] == bar_id, "compliance_mm_per_100kg"]
        ax.plot(pts, [i] * len(pts), "|", color=colour, ms=7, mew=1, alpha=0.6)
        ax.plot([lo, hi], [i, i], color=colour, lw=2, solid_capstyle="round")
        ax.plot(mean, i, marker, color=colour, ms=7, mec="white", mew=1)
        ax.text(max(hi, pts.max()) + 0.25, i, f"{mean:.1f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(b)), [bar_label(x) for x in b.index])
    ax.tick_params(axis="y", colors=INK, length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Compliance c (mm per 100 kg added mass)")
    ax.set_title(
        "Compliance per bar: mean, 95 % CI and single cycles",
        loc="left", fontsize=11, fontweight="bold",
    )  # fmt: skip
    _category_legend(ax, _present(list(b.index), categories), loc="lower right")
    return fig


def plot_h1(bars: pd.DataFrame, h1: pd.DataFrame):
    """H1: Nachgiebigkeit der Deadlift- gegen die Power-Stangen."""
    res = h1.iloc[0]
    fig, ax = plt.subplots(figsize=(5.2, 4.6), layout="constrained")
    for i, cat in enumerate(("power", "deadlift")):
        colour, marker, label = _style(cat)
        vals = bars.loc[bars["category"] == cat, "compliance_mm_per_100kg_mean"].to_numpy()
        vals = np.sort(vals)
        jitter = np.resize([-0.12, 0.0, 0.12, -0.06, 0.06], len(vals))
        ax.plot(i + jitter, vals, marker, color=colour, ms=8, mec="white", mew=1, ls="")
        ax.plot([i - 0.22, i + 0.22], [vals.mean()] * 2, color=INK, lw=1.6)
        ax.text(i + 0.26, vals.mean(), f"{vals.mean():.1f}", va="center", fontsize=9)
    ax.set_xticks([0, 1], [f"Power bars (n = {int(res['n_power'])})",
                           f"Deadlift bars (n = {int(res['n_deadlift'])})"])  # fmt: skip
    ax.tick_params(axis="x", colors=INK, length=0)
    ax.set_xlim(-0.5, 1.6)
    ax.set_ylim(bottom=0)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Compliance c (mm per 100 kg)")
    ax.set_title("H1: deadlift bars vs. power bars", loc="left", fontsize=11, fontweight="bold")
    ax.text(
        0.03, 0.05,
        f"Difference {res['mean_diff']:.1f} mm/100 kg · Hedges' g = {res['hedges_g']:.1f}\n"
        f"exact permutation p = {res['p_exact']:.4f} ({int(res['n_permutations'])} assignments)",
        transform=ax.transAxes, fontsize=8.5, color=MUTED, va="bottom",
    )  # fmt: skip
    return fig


def plot_h2(bars: pd.DataFrame, h2: pd.DataFrame, categories: dict[str, str]):
    """H2: Nichtlinearität, Restverformung und Hysterese je Stange gegen das MDC95-Band."""
    b = bars.set_index("bar_id")
    h = h2.set_index("bar_id")
    order = list(b.sort_values("compliance_mm_per_100kg_mean").index)
    panels = [
        ("nonlin_ring_moment_mm", "mdc95_dring_mm", "Non-linearity at peak\n(ΔD_ring vs. moment)"),
        ("residual_mm", "mdc95_d1_mm", "Residual deflection\nafter unloading"),
        ("hysteresis_mm", "mdc95_d1_mm", "Hysteresis\n(unloading − loading)"),
    ]
    fig, axes = plt.subplots(
        1, 3, figsize=(10, 0.36 * len(order) + 1.9), sharey=True, layout="constrained"
    )
    for ax, (col, mdc_col, title) in zip(axes, panels, strict=True):
        mdc = float(h[mdc_col].iloc[0])
        ax.axvspan(-mdc, mdc, color=GRID, alpha=0.7, lw=0)
        ax.axvline(0, color=MUTED, lw=0.8)
        for i, bar_id in enumerate(order):
            colour, marker, _ = _style(categories.get(bar_id, ""))
            lo, hi = b.loc[bar_id, f"{col}_ci_low"], b.loc[bar_id, f"{col}_ci_high"]
            ax.plot([lo, hi], [i, i], color=colour, lw=1.6, solid_capstyle="round")
            ax.plot(b.loc[bar_id, f"{col}_mean"], i, marker, color=colour, ms=6.5,
                    mec="white", mew=1)  # fmt: skip
        ax.set_title(f"{title}\nMDC95 = ±{mdc:.2f} mm", loc="left")
        ax.set_xlabel("mm")
        ax.grid(axis="y", visible=False)
        lim = max(mdc * 1.25, np.abs(ax.get_xlim()).max())
        ax.set_xlim(-lim, lim)
    axes[0].set_yticks(range(len(order)), [bar_label(x) for x in order])
    axes[0].tick_params(axis="y", colors=INK, length=0)
    handles = [
        Line2D([], [], color=_style(c)[0], marker=_style(c)[1], ls="", ms=6)
        for c in _present(order, categories)
    ] + [Line2D([], [], color=INK, lw=1.6), plt.Rectangle((0, 0), 1, 1, color=GRID)]
    labels = [_style(c)[2] for c in _present(order, categories)] + ["95 % CI", "within MDC95"]
    fig.legend(handles, labels, loc="outside lower center", ncols=len(labels))
    fig.suptitle(
        "H2: elastic behaviour – mean of three cycles per bar",
        x=0.01, ha="left", fontsize=11, fontweight="bold",
    )  # fmt: skip
    return fig


def make_all(
    deflection: pd.DataFrame,
    cycles: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    catalog: BarCatalog,
    out_dir: Path,
    formats: tuple[str, ...] = ("png",),
) -> list[Path]:
    """Alle Abbildungen nach ``out_dir`` schreiben; gibt die Pfade zurück."""
    out_dir.mkdir(parents=True, exist_ok=True)
    categories = {b.bar_id: b.category for b in catalog.bars}
    paths: list[Path] = []
    with plt.rc_context(RC):
        fig = plot_curve_grid(
            deflection, cycles, categories,
            x="added_mass_kg", y="delta_d1_mm",
            xlabel="Added mass (kg)", ylabel="ΔD1 (mm)",
            title="Centre deflection ΔD1 vs. added mass, three cycles per bar", fit_line=True,
        )  # fmt: skip
        paths += _save(fig, out_dir, "load_deflection_grid", formats)
        if {"load_moment_kgm", "delta_dring_mm"} <= set(deflection.columns):
            fig = plot_curve_grid(
                deflection, cycles, categories,
                x="load_moment_kgm", y="delta_dring_mm",
                xlabel="Load moment (kg·m)", ylabel="ΔD_ring (mm)",
                title="Deflection between the ring marks ΔD_ring vs. load moment", fit_line=False,
            )  # fmt: skip
            paths += _save(fig, out_dir, "dring_vs_moment_grid", formats)
        paths += _save(
            plot_overview(deflection, cycles, categories), out_dir, "load_deflection_overview",
            formats,
        )  # fmt: skip
        if "bars" in tables:
            fig = plot_compliance(cycles, tables["bars"], categories)
            paths += _save(fig, out_dir, "compliance_by_bar", formats)
        if {"bars", "h1"} <= set(tables):
            paths += _save(plot_h1(tables["bars"], tables["h1"]), out_dir, "h1_groups", formats)
        if {"bars", "h2"} <= set(tables):
            fig = plot_h2(tables["bars"], tables["h2"], categories)
            paths += _save(fig, out_dir, "h2_elasticity", formats)
    return paths
