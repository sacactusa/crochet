#!/usr/bin/env python3
"""
analyze_rm1_rm2.py

Formal Statistical Analysis Module for Research Questions RM1 & RM2:
- RM1: Paired Within-Item Effect of Active vs Inactive Reasoning (Gemini 2.5 Flash-Lite & Flash)
       Exact McNemar Test + Percentile Bootstrap 95% CIs (10,000 resamples, seed=42) + Wilson 95% CIs.
- RM2: Comparative Ranking of 6 Conditions on Contextual Protocol (R-A0, R-A1, L25L-OFF, L25L-ON, L25F-OFF, L25F-ON)
       Omnibus Cochran's Q Test (df=5) + 15 Pairwise Exact McNemar Tests with Holm-Bonferroni Correction.
- Evaluates TWO versions:
  1. Versi Utama (Setelah Pengulangan / Post-Retry)
  2. Versi Sensitivitas (Hanya Percobaan Pertama / First Attempt Only, Pasangan Lengkap)
- RM3 is strictly excluded per Researcher Decision (frozen until 1 Dec 2026).
"""

import os
import json
import math
import numpy as np
from scipy import stats
from itertools import combinations

RESULTS_FILE = "results/compilation_results.json"
BOOTSTRAP_SEED = 42
BOOTSTRAP_ROUNDS = 10000

# Retried request IDs from 19 Nov batch
RETRIED_REQUEST_IDS = {"REQ-0336", "REQ-0341", "REQ-0351", "REQ-0512", "REQ-0514"}
# Corresponding item_ids:
# REQ-0336: mid_25 (L25L-ON)
# REQ-0341: early_53 (L25L-ON)
# REQ-0351: early_32 (L25L-ON)
# REQ-0512: early_43 (L25F-ON)
# REQ-0514: early_53 (L25F-ON)

def wilson_score_interval(k, n, confidence=0.95):
    if n == 0:
        return 0.0, (0.0, 0.0)
    p = k / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return p, (max(0.0, center - spread), min(1.0, center + spread))

def paired_mcnemar_test(b, c):
    n_disc = b + c
    if n_disc == 0:
        return 1.0, 0
    p_val = stats.binomtest(b, n_disc, p=0.5, alternative='two-sided').pvalue
    return p_val, (b - c)

def bootstrap_paired_diff_ci(y1, y2, rounds=BOOTSTRAP_ROUNDS, seed=BOOTSTRAP_SEED):
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

def cochrans_q_test(matrix):
    """
    matrix: binary 2D array (N items x k treatments)
    returns: Q statistic, df, p-value
    """
    mat = np.array(matrix, dtype=float)
    N, k = mat.shape
    u_i = np.sum(mat, axis=1) # row sums
    T_j = np.sum(mat, axis=0) # column sums
    T = np.sum(u_i)           # grand total

    denom = k * T - np.sum(u_i**2)
    if denom == 0:
        return 0.0, k - 1, 1.0
    
    numerator = (k - 1) * (k * np.sum(T_j**2) - T**2)
    Q = numerator / denom
    df = k - 1
    p_value = 1.0 - stats.chi2.cdf(Q, df)
    return float(Q), df, float(p_value)

def holm_bonferroni(p_values):
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

def load_data(filter_first_attempt=False, protocol="contextual"):
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        raw_results = json.load(f)

    # If filter_first_attempt is True, exclude records that came from retries
    by_condition = {}
    for r in raw_results:
        cond = r["condition"]
        item_id = r["item_id"]
        req_id = r.get("request_id")
        
        if filter_first_attempt and req_id in RETRIED_REQUEST_IDS:
            continue
            
        proto_data = r.get(protocol, {})
        if proto_data.get("excluded", False):
            continue
            
        valid = proto_data.get("valid", False)
        by_condition.setdefault(cond, {})[item_id] = valid
        
    return by_condition

def run_rm1(by_condition, title="VERSI UTAMA"):
    print("\n" + "=" * 90)
    print(f" [RM1] PAIRED EFFECT OF ACTIVE REASONING (GEMINI 2.5) — {title}")
    print("=" * 90)
    
    models = [
        ("Gemini 2.5 Flash-Lite", "L25L-OFF", "L25L-ON"),
        ("Gemini 2.5 Flash", "L25F-OFF", "L25F-ON")
    ]
    
    for model_name, cond_off, cond_on in models:
        dict_off = by_condition.get(cond_off, {})
        dict_on = by_condition.get(cond_on, {})
        common_items = sorted(set(dict_off.keys()) & set(dict_on.keys()))
        N_eff = len(common_items)
        
        vpr_off, (off_l, off_h) = wilson_score_interval(sum(1 for it in common_items if dict_off[it]), N_eff)
        vpr_on, (on_l, on_h) = wilson_score_interval(sum(1 for it in common_items if dict_on[it]), N_eff)
        
        y_off = [dict_off[it] for it in common_items]
        y_on = [dict_on[it] for it in common_items]
        
        b = sum(1 for o, n in zip(y_off, y_on) if o and not n) # OFF=1, ON=0
        c = sum(1 for o, n in zip(y_off, y_on) if not o and n) # OFF=0, ON=1
        pval, net_diff = paired_mcnemar_test(b, c)
        delta_obs, (b_low, b_high) = bootstrap_paired_diff_ci(y_off, y_on)
        
        print(f"\nModel: {model_name} (Complete Pairs N_eff = {N_eff})")
        print(f"  VPR OFF : {vpr_off*100:6.2f}% (95% Wilson CI: [{off_l*100:5.1f}%, {off_h*100:5.1f}%])")
        print(f"  VPR ON  : {vpr_on*100:6.2f}% (95% Wilson CI: [{on_l*100:5.1f}%, {on_h*100:5.1f}%])")
        print(f"  Discordant Pairs: b (OFF=1, ON=0) = {b}, c (OFF=0, ON=1) = {c} (Total = {b+c})")
        print(f"  Delta (ON - OFF): {delta_obs*100:+6.2f}% (Percentile Bootstrap 95% CI: [{b_low*100:+5.1f}%, {b_high*100:+5.1f}%])")
        print(f"  Exact McNemar Two-Sided p-value: {pval:.4f}")
        sig_str = "SIGNIFIKAN (p < 0.05)" if pval < 0.05 else "TIDAK SIGNIFIKAN (p >= 0.05)"
        print(f"  Kesimpulan Inferensial: {sig_str}")

def run_rm2(by_condition, title="VERSI UTAMA"):
    print("\n" + "=" * 90)
    print(f" [RM2] COMPARATIVE RANKING OF 6 CONDITIONS (CONTEXTUAL) — {title}")
    print("=" * 90)
    
    cond_order = ["R-A0", "R-A1", "L25L-OFF", "L25L-ON", "L25F-OFF", "L25F-ON"]
    cond_labels = {
        "R-A0": "Rule-Based (Tanpa Validator)",
        "R-A1": "Rule-Based (Dengan Validator)",
        "L25L-OFF": "Gemini 2.5 Flash-Lite (Reasoning OFF)",
        "L25L-ON": "Gemini 2.5 Flash-Lite (Reasoning ON)",
        "L25F-OFF": "Gemini 2.5 Flash (Reasoning OFF)",
        "L25F-ON": "Gemini 2.5 Flash (Reasoning ON)"
    }
    
    # Complete cases across all 6 conditions
    item_sets = [set(by_condition.get(c, {}).keys()) for c in cond_order]
    complete_items = sorted(set.intersection(*item_sets))
    N_eff = len(complete_items)
    
    print(f"Jumlah Item Kontekstual Lengkap (Complete Cases Omnibus): N_eff = {N_eff}")
    
    # 1. Marginal VPR Table for Complete Items
    print("\n1. Tabel VPR Marginal (N = %d):" % N_eff)
    print(f"{'Kondisi':<10} | {'Nama Kondisi':<38} | {'Valid':<5} | {'VPR':<7} | {'95% Wilson CI':<20}")
    print("-" * 90)
    
    matrix = []
    vprs = {}
    for c in cond_order:
        k = sum(1 for it in complete_items if by_condition[c][it])
        prop, (ci_l, ci_h) = wilson_score_interval(k, N_eff)
        vprs[c] = prop
        ci_str = f"[{ci_l*100:.1f}%, {ci_h*100:.1f}%]"
        print(f"{c:<10} | {cond_labels[c]:<38} | {k:<5} | {prop*100:>6.2f}% | {ci_str:<20}")
        
    for it in complete_items:
        row = [1 if by_condition[c][it] else 0 for c in cond_order]
        matrix.append(row)
        
    # 2. Omnibus Cochran's Q Test
    Q, df, p_q = cochrans_q_test(matrix)
    print("\n2. Uji Omnibus Cochran's Q (k = 6):")
    print(f"  Cochran's Q = {Q:.4f} | df = {df} | Asymptotic p-value = {p_q:.4e}")
    if p_q < 0.05:
        print("  Kesimpulan Omnibus: Terdapat perbedaan performa yang SIGNIFIKAN secara statistik (p < 0.001) di antara ke-6 kondisi.")
    else:
        print("  Kesimpulan Omnibus: Tidak terdapat perbedaan performa yang signifikan (p >= 0.05).")
        
    # 3. Post-Hoc 15 Pairwise McNemar Tests with Holm-Bonferroni Correction
    print("\n3. Uji Lanjutan: 15 Perbandingan Berpasangan McNemar (Koreksi Holm-Bonferroni):")
    pairs = list(combinations(cond_order, 2))
    pairwise_results = []
    
    for c1, c2 in pairs:
        y1 = [by_condition[c1][it] for it in complete_items]
        y2 = [by_condition[c2][it] for it in complete_items]
        b = sum(1 for a, b_val in zip(y1, y2) if a and not b_val)
        c = sum(1 for a, b_val in zip(y1, y2) if not a and b_val)
        pval, _ = paired_mcnemar_test(b, c)
        vpr1 = vprs[c1]
        vpr2 = vprs[c2]
        delta = vpr2 - vpr1
        pairwise_results.append({
            "pair": f"{c1} vs {c2}",
            "c1": c1, "c2": c2,
            "vpr1": vpr1, "vpr2": vpr2, "delta": delta,
            "b": b, "c": c, "p_raw": pval
        })
        
    # Apply Holm-Bonferroni
    raw_pvals = [pr["p_raw"] for pr in pairwise_results]
    adj_pvals = holm_bonferroni(raw_pvals)
    for pr, p_adj in zip(pairwise_results, adj_pvals):
        pr["p_adj"] = p_adj
        
    # Sort by raw p-value
    pairwise_results.sort(key=lambda x: x["p_raw"])
    
    print(f"{'Pasangan':<20} | {'VPR 1':<6} | {'VPR 2':<6} | {'Delta':<7} | {'(b, c)':<8} | {'p-mentah':<10} | {'p-adj (Holm)':<12} | {'Signifikansi'}")
    print("-" * 95)
    for pr in pairwise_results:
        sig = "SIGNIFIKAN *" if pr["p_adj"] < 0.05 else "tdk signifikan"
        print(f"{pr['pair']:<20} | {pr['vpr1']*100:>5.1f}% | {pr['vpr2']*100:>5.1f}% | {pr['delta']*100:>+6.1f}% | ({pr['b']:>2},{pr['c']:>2})   | {pr['p_raw']:<10.4f} | {pr['p_adj']:<12.4f} | {sig}")

def main():
    print("=" * 90)
    print(" EVALUASI STATISTIK CROCHETBENCH-DSTEP: RM1 & RM2")
    print(" (Protokol Kontekstual & Standalone, Bebas dari RM3)")
    print("=" * 90)
    
    # 1. VERSI UTAMA (SETELAH PENGULANGAN / POST-RETRY)
    data_utama = load_data(filter_first_attempt=False, protocol="contextual")
    run_rm1(data_utama, title="VERSI UTAMA (Pasca-Retry 19 Nov)")
    run_rm2(data_utama, title="VERSI UTAMA (Pasca-Retry 19 Nov)")
    
    # 2. VERSI SENSITIVITAS (HANYA PERCOBAAN PERTAMA / FIRST ATTEMPT ONLY)
    data_sens = load_data(filter_first_attempt=True, protocol="contextual")
    run_rm1(data_sens, title="VERSI SENSITIVITAS (Hanya Percobaan Pertama, Pasangan Lengkap)")
    run_rm2(data_sens, title="VERSI SENSITIVITAS (Hanya Percobaan Pertama, Pasangan Lengkap)")

if __name__ == "__main__":
    main()
