import numpy as np
import pandas as pd
import pytest
from scipy import stats as st

from barbellscan.config import load_analysis, load_bars
from barbellscan.deflection import add_deflection, apply_exclusions, cycle_summary
from barbellscan.stats import (
    hedges_g,
    icc_oneway,
    mean_ci,
    permutation_test_greater,
    run_all,
    tost_one_sample,
    welch_diff,
)

BARS = load_bars()
CFG = load_analysis()
E_STEEL, G = 210e9, 9.81


def _beam(bar, n, cfg=CFG):
    """Euler-Bernoulli-Balken auf zwei Auflagern: (ΔD1, ΔD_ring) in mm für n Scheiben je Seite."""
    geo = cfg.geometry
    a, t = geo.support_offset_loaded_mm, geo.plate_thickness_mm
    stop = bar.shaft_length_mm / 2
    loads = [(stop + (k + 0.5) * t, cfg.plate_mass_kg) for k in range(n)]
    if n:
        loads.append((stop + n * t + geo.collar_centre_mm, cfg.collar_mass_kg))
    ei = E_STEEL * np.pi * (bar.shaft_diameter_mm / 1000) ** 4 / 64
    h = 0.5
    x = np.arange(0, bar.total_length_mm / 2 + geo.ball_offset_mm + h, h)
    moment = np.zeros_like(x)
    for xi, m in loads:
        moment += np.where(x <= a, m * G * (xi - a), np.where(x < xi, m * G * (xi - x), 0)) / 1000
    kappa = moment / ei / 1000  # 1/mm
    theta = np.concatenate([[0], np.cumsum((kappa[1:] + kappa[:-1]) / 2 * h)])
    y = -np.concatenate([[0], np.cumsum((theta[1:] + theta[:-1]) / 2 * h)])
    return y[0] - y[-1], y[0] - np.interp(bar.ring_spacing_mm / 2, x, y)


def _tracking(bar_ids=None, noise=0.0, seed=0):
    """Tracking-Tabelle (px) eines ideal elastischen Balkens, 2 px/mm."""
    rng = np.random.default_rng(seed)
    rows = []
    for bar in BARS.bars:
        if bar_ids and bar.bar_id not in bar_ids:
            continue
        for cycle in CFG.cycles:
            for s in CFG.schedule():
                d1, dring = _beam(bar, s.plates_per_side)
                rows.append(
                    {
                        "bar_id": bar.bar_id,
                        "cycle": cycle,
                        "step": s.step,
                        "phase": s.phase,
                        "plates_per_side": s.plates_per_side,
                        "added_mass_kg": s.added_mass_kg,
                        "image_path": f"raw/{bar.photo_prefix}{cycle}{s.step:04d}.JPG",
                        "qc_flags": "blur" if s.step == 3 else "",
                        "ring_dist_px": 2 * bar.ring_spacing_mm,
                        "ball_dist_px": 2 * bar.ball_span_mm(35),
                        "d1_px": 2 * (d1 + 1.5 + rng.normal(0, noise)),
                        "dring_px": 2 * (dring + 0.2 + rng.normal(0, noise)),
                        "detect_flags": "",
                    }
                )
    return pd.DataFrame(rows)


def test_load_moment_grows_faster_than_mass():
    bar = BARS.bar("ohio_power")
    m = [CFG.load_moment_kgm(n, bar) for n in range(9)]
    assert m[0] == 0
    # erste Scheibe: Hebelarm 654 + 13,5 - 362,5 mm; Klemme 654 + 27 + 15 - 362,5 mm
    assert m[1] == pytest.approx(2 * (25 * 0.305 + 2.5 * 0.3335))
    steps = np.diff(m)
    assert np.all(np.diff(steps[1:]) > 0)  # jede weitere Scheibe sitzt weiter außen


def test_elastic_beam_is_linear_in_moment_for_dring_but_not_in_mass():
    df = add_deflection(_tracking(["ohio_power", "texas_deadlift"]), BARS, CFG)
    cyc = cycle_summary(df, CFG)
    assert cyc["nonlin_ring_moment_mm"].abs().max() < 0.01
    assert cyc["nonlin_at_peak_mm"].min() > 1.0  # gegen die Masse: geometrisch gekrümmt
    assert cyc["nonlin_d1_moment_mm"].min() > 0.2  # ΔD1 enthält die Biegung im Lastbereich
    assert cyc["residual_mm"].abs().max() < 1e-9
    assert cyc["hysteresis_mm"].abs().max() < 1e-9


def test_exclusions_blank_values_and_validate_input():
    tr = _tracking(["ohio_power"])
    excl = pd.DataFrame({"image": ["OhioPowerA0005.JPG"], "reason": ["Band verdeckt (Overlay)"]})
    df = add_deflection(tr, BARS, CFG, excl)
    hit = df["image_path"].str.endswith("OhioPowerA0005.JPG")
    assert df.loc[hit, "delta_d1_mm"].isna().all()
    assert df.loc[hit, "deflection_flags"].iloc[0] == "excluded"
    assert df.loc[~hit, "delta_d1_mm"].notna().all()
    assert cycle_summary(df, CFG).set_index("cycle").loc["A", "n_up"] == 8
    with pytest.raises(ValueError, match="passt auf 0"):
        apply_exclusions(tr, pd.DataFrame({"image": ["Tippfehler.JPG"], "reason": ["x"]}))
    with pytest.raises(ValueError, match="ohne Begründung"):
        apply_exclusions(tr, pd.DataFrame({"image": ["OhioPowerA0005.JPG"], "reason": [None]}))


def test_drop_qc_flags_for_sensitivity_analysis():
    df = add_deflection(_tracking(["ohio_power"]), BARS, CFG, drop_qc_flags=["blur"])
    dropped = df[df["exclusion_reason"] == "qc_flag:blur"]
    assert len(dropped) == 3 and (dropped["step"] == 3).all()
    assert dropped["delta_d1_mm"].isna().all()


def test_permutation_test_is_exact():
    res = permutation_test_greater([10, 11, 12], [1, 2, 3, 4, 5, 6, 7, 8])
    assert res["n_permutations"] == 165
    assert res["p_exact"] == pytest.approx(1 / 165)
    assert res["mean_diff"] == pytest.approx(11 - 4.5)
    # kleinster Wert in der Deadlift-Gruppe: nur die Zuordnung mit drei größeren ist extremer
    worst = permutation_test_greater([1, 2, 3], [4, 5, 6, 7, 8, 9, 10, 11])
    assert worst["p_exact"] == pytest.approx(1.0)
    # Gleichstand zählt als mindestens so extrem
    assert permutation_test_greater([2, 2], [2, 2])["p_exact"] == pytest.approx(1.0)


def test_permutation_test_matches_scipy():
    rng = np.random.default_rng(3)
    a, b = rng.normal(1, 1, 3), rng.normal(0, 1, 8)
    ref = st.permutation_test(
        (a, b),
        lambda x, y: x.mean() - y.mean(),
        permutation_type="independent",
        alternative="greater",
        n_resamples=np.inf,
    )
    assert permutation_test_greater(a, b)["p_exact"] == pytest.approx(ref.pvalue)


def test_hedges_g_reference():
    a, b = np.array([2.0, 4, 6]), np.array([1.0, 2, 3, 4, 5])
    pooled = np.sqrt((2 * a.var(ddof=1) + 4 * b.var(ddof=1)) / 6)
    assert hedges_g(a, b) == pytest.approx((4 - 3) / pooled * (1 - 3 / 23))


def test_icc_matches_shrout_fleiss_1979():
    # Shrout & Fleiss (1979), Tabelle 2: 6 Targets x 4 Rater, ICC(1,1) = 0,17
    ratings = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]
    values = pd.Series(np.ravel(ratings), dtype=float)
    groups = pd.Series(np.repeat(np.arange(6), 4))
    res = icc_oneway(values, groups)
    assert res["icc_1_1"] == pytest.approx(0.1657, abs=1e-3)
    assert res["ms_between"] == pytest.approx(11.24, abs=0.01)
    assert res["sem"] == pytest.approx(np.sqrt(6.26), abs=0.01)
    assert res["mdc95"] == pytest.approx(1.96 * np.sqrt(2) * res["sem"])


def test_icc_handles_missing_cycle():
    values = pd.Series([1.0, 1.1, 0.9, 2.0, 2.1, np.nan, 3.0, 3.1, 2.9])
    res = icc_oneway(values, pd.Series(np.repeat(["a", "b", "c"], 3)))
    assert res["n_obs"] == 8 and res["n_bars"] == 3
    assert 0.9 < res["icc_1_1"] < 1


def test_welch_and_mean_ci_match_scipy():
    a, b = [10.1, 10.4, 9.9], [9.0, 9.6, 9.2]
    ref = st.ttest_ind(a, b, equal_var=False).confidence_interval(0.95)
    res = welch_diff(a, b)
    assert (res["ci_low"], res["ci_high"]) == pytest.approx((ref.low, ref.high))
    ci = mean_ci(a)
    ref1 = st.ttest_1samp(a, 0).confidence_interval(0.95)
    assert (ci["ci_low"], ci["ci_high"]) == pytest.approx((ref1.low, ref1.high))


def test_tost_matches_two_one_sided_t_tests():
    x = [0.05, -0.02, 0.08]
    res = tost_one_sample(x, 0.5)
    p_low = st.ttest_1samp(x, -0.5, alternative="greater").pvalue
    p_high = st.ttest_1samp(x, 0.5, alternative="less").pvalue
    assert res["p_tost"] == pytest.approx(max(p_low, p_high))
    assert res["equivalent"]
    assert not tost_one_sample([0.6, 0.7, 0.65], 0.5)["equivalent"]
    assert not tost_one_sample(x, float("nan"))["equivalent"]


def test_run_all_on_elastic_beam_dataset():
    df = add_deflection(_tracking(noise=0.05, seed=1), BARS, CFG)
    tables = run_all(cycle_summary(df, CFG), BARS, CFG)
    assert set(tables) == {"bars", "categories", "h1", "pairs", "reliability", "h2"}
    h1 = tables["h1"].iloc[0]
    # 27-mm-Deadlift-Stangen sind im Balkenmodell klar nachgiebiger: kleinster möglicher p-Wert
    assert h1["n_deadlift"] == 3 and h1["n_power"] == 8
    assert h1["p_exact"] == pytest.approx(1 / 165) and h1["significant"]
    assert len(tables["bars"]) == 13 and (tables["bars"]["n_cycles"] == 3).all()
    b = tables["bars"].set_index("bar_id")
    assert b.loc["ohio_power", "stiffness_kg_per_mm"] == pytest.approx(
        100 / b.loc["ohio_power", "compliance_mm_per_100kg_mean"]
    )
    rel = tables["reliability"].set_index("quantity")
    assert rel.loc["compliance_mm_per_100kg", "icc_1_1"] > 0.99
    assert 0.05 < rel.loc["delta_d1_peak_mm", "mdc95"] < 0.5
    h2 = tables["h2"]
    assert h2["linear_within_mdc95"].all()
    assert h2["hysteresis_within_mdc95"].all()
    assert len(tables["pairs"]) == 6
