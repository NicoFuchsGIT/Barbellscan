import pandas as pd

from barbellscan.config import load_analysis, load_bars
from barbellscan.deflection import add_deflection, cycle_summary
from barbellscan.plots import _spread_labels, bar_label, make_all
from barbellscan.stats import run_all
from test_stats import _tracking


def test_bar_label():
    assert bar_label("eleiko_comp_2016") == "Eleiko Comp 2016"
    assert bar_label("zkc_iwf") == "ZKC IWF"


def test_spread_labels_keeps_order_and_gap():
    values = pd.Series([10.0, 10.2, 10.3, 30.0]).to_numpy()
    pos = _spread_labels(values, 2.0)
    assert (pos[1:] - pos[:-1] >= 2.0 - 1e-9).all()


def test_make_all_writes_every_figure(tmp_path):
    bars, cfg = load_bars(), load_analysis()
    df = add_deflection(_tracking(noise=0.05, seed=1), bars, cfg)
    cyc = cycle_summary(df, cfg)
    paths = make_all(df, cyc, run_all(cyc, bars, cfg), bars, tmp_path, ("png",))
    assert {p.stem for p in paths} == {
        "load_deflection_grid",
        "dring_vs_moment_grid",
        "load_deflection_overview",
        "compliance_by_bar",
        "h1_groups",
        "h2_elasticity",
    }
    assert all(p.stat().st_size > 10_000 for p in paths)
    # ohne Statistik-Tabellen entstehen nur die Kurven
    assert len(make_all(df, cyc, {}, bars, tmp_path / "curves")) == 3
