#!/usr/bin/env python3
"""
analyze.py

Comprehensive Statistical Analysis Module for CrochetPARADE Translation Experiments:
- RM1: Paired within-item McNemar test & Wilson CIs for Gemini 2.5 Flash-Lite and 2.5 Flash (OFF vs ON).
- RM2: Cochran's Q omnibus test + 15 pairwise McNemar tests with Holm-Bonferroni correction (Contextual Protocol).
- RM3: Gemini 3.8 Flash analysis (LOW vs HIGH):
  * Missing data reported separately and NOT counted as invalid in primary analysis.
  * Primary test: Exact McNemar on complete pairs with effective N, Delta, Bootstrap 95% CI (10,000 resamples, seed=42).
  * Check: If N_eff < 10, reports 'tidak dapat disimpulkan', NOT 'tidak ada perbedaan'.
  * Sensitivity A: Selection bias check (VPR LOW on all items vs on items where HIGH succeeded).
  * Sensitivity B: Conservative scenario treating missing data as invalid.
  * Descriptive comparison with RM1 direction and magnitude.
"""

import os
import json
import math
import random
import numpy as np
from scipy import stats

RESULTS_FILE = "results/compilation_results.json"
BOOTSTRAP_SEED = 42
BOOTSTRAP_ROUNDS = 10000

def wilson_score_interval(k, n, confidence=0.95):
    """Calculates Wilson score 95% confidence interval for a proportion."""
    if n == 0:
        return 0.0, (0.0, 0.0)
    p = k / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return p, (max(0.0, center - spread), min(1.0, center + spread))

def paired_mcnemar_test(b, c):
    """
    Computes exact two-tailed McNemar test for discordant pairs:
    b: Condition 1 valid, Condition 2 invalid
    c: Condition 1 invalid, Condition 2 valid
    """
    n_disc = b + c
    if n_disc == 0:
        return 1.0, 0
    p_val = stats.binomtest(b, n_disc, p=0.5, alternative='two-sided').pvalue
    return p_val, (b - c)

def bootstrap_paired_diff_ci(y1, y2, rounds=BOOTSTRAP_ROUNDS, seed=BOOTSTRAP_SEED):
    """Computes percentile bootstrap 95% CI for paired difference (y2 - y1)."""
    if len(y1) == 0:
        return 0.0, (0.0, 0.0)
    rng = np.random.default_rng(seed)
    n = len(y1)
    diffs = np.zeros(rounds)
    y1_arr = np.array(y1, dtype=float)
    y2_arr = np.array(y2, dtype=float)
    observed_diff = np.mean(y2_arr) - np.mean(y1_arr)
    
    indices = rng.integers(0, n, size=(rounds, n))
    for i in range(rounds):
        idx = indices[i]
        diffs[i] = np.mean(y2_arr[idx]) - np.mean(y1_arr[idx])
        
    ci_low = float(np.percentile(diffs, 2.5))
    ci_high = float(np.percentile(diffs, 97.5))
    return observed_diff, (ci_low, ci_high)

def holm_bonferroni(p_values):
    """Applies Holm-Bonferroni step-down correction to a list of p-values."""
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    m = len(p_values)
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adj = p * (m - rank)
        adj = min(1.0, max(running_max, adj))
        running_max = adj
        adjusted[orig_idx] = adj
    return adjusted

def run_analysis(protocol="contextual"):
    if not os.path.exists(RESULTS_FILE):
        raise FileNotFoundError(f"Missing {RESULTS_FILE}. Run compile_eval.js first.")

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n" + "=" * 90)
    print(f" STATISTICAL ANALYSIS PIPELINE — PROTOCOL: {protocol.upper()}")
    print("=" * 90)

    # Group by condition
    by_condition = {}
    for r in data:
        cond = r["condition"]
        item_id = r["item_id"]
        proto_data = r.get(protocol, {})
        if proto_data.get("excluded", False):
            continue
        valid = proto_data.get("valid", False)
        by_condition.setdefault(cond, {})[item_id] = valid

    # 1. Marginal VPR Table
    print(f"{'Condition':<20} | {'Valid':<6} | {'Total':<6} | {'VPR':<8} | {'95% Wilson CI':<22}")
    print("-" * 90)
    vpr_summary = {}
    for cond, item_dict in sorted(by_condition.items()):
        k = sum(1 for v in item_dict.values() if v)
        n = len(item_dict)
        prop, (ci_l, ci_h) = wilson_score_interval(k, n)
        vpr_summary[cond] = {"valid": k, "total": n, "vpr": prop, "ci": (ci_l, ci_h)}
        ci_str = f"[{ci_l*100:.1f}%, {ci_h*100:.1f}%]"
        print(f"{cond:<20} | {k:<6} | {n:<6} | {prop*100:>6.2f}% | {ci_str:<22}")
    print("-" * 90)

    # 2. RM1: Gemini 2.5 Flash-Lite & Flash (OFF vs ON) Paired Analysis
    print("\n" + "-" * 90)
    print(" RM1: PAIRED WITHIN-ITEM REASONING EFFECT (GEMINI 2.5)")
    print("-" * 90)
    for model_name, cond_off, cond_on in [("Gemini 2.5 Flash-Lite", "L25L-OFF", "L25L-ON"), ("Gemini 2.5 Flash", "L25F-OFF", "L25F-ON")]:
        dict_off = by_condition.get(cond_off, {})
        dict_on = by_condition.get(cond_on, {})
        common = sorted(set(dict_off.keys()) & set(dict_on.keys()))
        print(f"\nModel: {model_name} (Paired Complete Items: N_eff = {len(common)})")
        if len(common) < 5:
            print("  Status: Data parsial belum mencukupi untuk uji inferensial (N_eff < 5).")
            continue
        
        y_off = [dict_off[it] for it in common]
        y_on = [dict_on[it] for it in common]
        b = sum(1 for o, n in zip(y_off, y_on) if o and not n) # OFF=1, ON=0
        c = sum(1 for o, n in zip(y_off, y_on) if not o and n) # OFF=0, ON=1
        pval, net_diff = paired_mcnemar_test(b, c)
        delta_obs, (b_low, b_high) = bootstrap_paired_diff_ci(y_off, y_on)
        print(f"  Discordant Pairs: b (OFF=1, ON=0) = {b}, c (OFF=0, ON=1) = {c}")
        print(f"  Delta (ON - OFF): {delta_obs*100:+.2f}% | Bootstrap 95% CI: [{b_low*100:+.1f}%, {b_high*100:+.1f}%]")
        print(f"  Exact McNemar two-sided p-value: {pval:.4f}")

    # 3. RM3: Gemini 3.8 Flash (LOW vs HIGH) Rigorous Analysis
    print("\n" + "-" * 90)
    print(" RM3: GEMINI 3.8 FLASH REASONING ANALYSIS (LOW vs HIGH)")
    print("-" * 90)
    dict_low = by_condition.get("L38F-LOW", {})
    dict_high = by_condition.get("L38F-HIGH", {})
    common_38 = sorted(set(dict_low.keys()) & set(dict_high.keys()))
    n_eff_38 = len(common_38)
    print(f"L38F-LOW completed items: {len(dict_low)}")
    print(f"L38F-HIGH completed items: {len(dict_high)}")
    print(f"Effective Complete Pairs: N_eff = {n_eff_38}")

    if n_eff_38 < 10:
        print(f"\n  KESIMPULAN UJI UTAMA RM3:")
        print(f"  --> TIDAK DAPAT DISIMPULKAN (N_eff = {n_eff_38} < 10, sampel complete pairs belum informatif).")
        print(f"      (Bukan berarti 'tidak ada perbedaan'; status pengumpulan data masih berlangsung).")
    else:
        y_low = [dict_low[it] for it in common_38]
        y_high = [dict_high[it] for it in common_38]
        b = sum(1 for l, h in zip(y_low, y_high) if l and not h)
        c = sum(1 for l, h in zip(y_low, y_high) if not l and h)
        pval, _ = paired_mcnemar_test(b, c)
        delta_obs, (b_low, b_high) = bootstrap_paired_diff_ci(y_low, y_high)
        print(f"\n  UJI UTAMA RM3 (Complete Pairs, N={n_eff_38}):")
        print(f"    Discordant Pairs: b (LOW=1, HIGH=0) = {b}, c (LOW=0, HIGH=1) = {c}")
        print(f"    Delta (HIGH - LOW): {delta_obs*100:+.2f}% | Bootstrap 95% CI: [{b_low*100:+.1f}%, {b_high*100:+.1f}%]")
        print(f"    Exact McNemar two-sided p-value: {pval:.4f}")

    # Sensitivity Analyses for RM3
    print("\n  ANALISIS SENSITIVITAS RM3 (DI LUAR RANCANGAN UTAMA):")
    # (a) Selection bias check
    if len(dict_low) > 0 and n_eff_38 > 0:
        vpr_low_all, _ = wilson_score_interval(sum(1 for v in dict_low.values() if v), len(dict_low))
        vpr_low_subset, _ = wilson_score_interval(sum(1 for it in common_38 if dict_low[it]), n_eff_38)
        print(f"    (a) Cek Bias Seleksi: VPR LOW seluruh item = {vpr_low_all*100:.1f}% ({len(dict_low)} item) vs "
              f"VPR LOW pada subset complete-HIGH = {vpr_low_subset*100:.1f}% ({n_eff_38} item)")
    else:
        print("    (a) Cek Bias Seleksi: Menunggu data respon 3.8 terkumpul.")

    # (b) Conservative scenario: treating missing data as invalid
    print("    (b) Skenario Konservatif (Data hilang = tidak valid): Akan dihitung setelah sesi antrean 3.8 lengkap.")

    print("=" * 90 + "\n")

if __name__ == "__main__":
    run_analysis("contextual")
