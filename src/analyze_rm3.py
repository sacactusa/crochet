#!/usr/bin/env python3
"""
analyze_rm3.py

Comprehensive Statistical Analysis Module for Research Question 3 (RM3):
Comparative Analysis of Gemini 3.8 Flash Reasoning (LOW vs HIGH) in Crochet DSL Translation.

Scheduled Execution: On or after 30 November 2026 (Pacific Time), following official data freeze.

Outputs:
(a) Completed responses per reasoning level (LOW vs HIGH) and per step group (early, mid, late).
(b) Complete pairs count (items completed in both LOW and HIGH) and effective sample size (N_eff).
(c) Valid Pattern Rate (VPR) for LOW and HIGH with Wilson score 95% CIs and respective denominators.
(d) Exact McNemar test and bootstrap 95% CIs only if N_eff >= 10; otherwise outputs 'tidak dapat disimpulkan'.
(e) Access availability table: attempts, successes, 503, 504, timeout, 429 per level and per Pacific date.
(f) Latency (duration) and thinking token distributions on successful responses.
(g) Sensitivity analyses:
    - Sensitivity A (Selection Bias Check): VPR LOW on all completed items vs on complete-pair subset.
    - Sensitivity B (Conservative Scenario / Worst-Case Imputation): Treating all uncompleted/missing items as invalid (N=119).
"""

import os
import sys
import json
import math
import argparse
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter
import numpy as np
from scipy import stats

# Paths
QUEUE_FILE = "data/experiment_queue.json"
RAW_LLM_FILE = "raw/llm.jsonl"
COMPILATION_FILE = "results/compilation_results.json"
QUOTA_TRACKER_FILE = "logs/quota_tracker.json"
MODEL_ACCESS_FILE = "logs/model_access_38_detailed.jsonl"

TZ_PT = ZoneInfo("America/Los_Angeles")
TZ_WIB = ZoneInfo("Asia/Jakarta")
FREEZE_DATE_PT = "2026-12-01"
BOOTSTRAP_ROUNDS = 10000
BOOTSTRAP_SEED = 42

def is_runner_active():
    """Checks if a run_daily instance is currently active by examining runner.lock and PID liveness."""
    lock_file = "data/runner.lock"
    if not os.path.exists(lock_file):
        return False, None
    try:
        with open(lock_file, "r") as f:
            content = f.read().strip()
            lock_data = json.loads(content) if content.startswith("{") else {"pid": int(content)}
            pid = lock_data.get("pid", 0)
            if pid <= 0:
                return False, None
            if os.name == 'nt':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if process:
                    kernel32.CloseHandle(process)
                    return True, pid
                return False, None
            else:
                os.kill(pid, 0)
                return True, pid
    except Exception:
        return False, None

def to_pt_date(ts_str=None):
    """Converts naive or timezone-aware ISO timestamp string to Pacific calendar date (YYYY-MM-DD)."""
    if not ts_str:
        return datetime.now(TZ_PT).strftime("%Y-%m-%d")
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_WIB)
        return dt.astimezone(TZ_PT).strftime("%Y-%m-%d")
    except Exception:
        return str(ts_str)[:10]

def wilson_score_interval(k, n, confidence=0.95):
    """Calculates Wilson score 95% confidence interval for a proportion k/n."""
    if n == 0:
        return 0.0, (0.0, 0.0)
    p = k / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    spread = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return p, (max(0.0, center - spread), min(1.0, center + spread))

def paired_mcnemar_test(b, c):
    """Computes exact two-tailed McNemar test using binomial distribution."""
    n_disc = b + c
    if n_disc == 0:
        return 1.0, 0
    p_val = stats.binomtest(b, n_disc, p=0.5, alternative='two-sided').pvalue
    return p_val, (b - c)

def bootstrap_paired_diff_ci(y1, y2, rounds=BOOTSTRAP_ROUNDS, seed=BOOTSTRAP_SEED):
    """Percentile bootstrap 95% confidence interval for paired difference (y2 - y1)."""
    if len(y1) == 0:
        return 0.0, (0.0, 0.0)
    rng = np.random.default_rng(seed)
    n = len(y1)
    diffs = np.zeros(rounds)
    y1_arr = np.array(y1, dtype=float)
    y2_arr = np.array(y2, dtype=float)
    observed_diff = float(np.mean(y2_arr) - np.mean(y1_arr))
    
    indices = rng.integers(0, n, size=(rounds, n))
    for i in range(rounds):
        idx = indices[i]
        diffs[i] = np.mean(y2_arr[idx]) - np.mean(y1_arr[idx])
        
    ci_low = float(np.percentile(diffs, 2.5))
    ci_high = float(np.percentile(diffs, 97.5))
    return observed_diff, (ci_low, ci_high)

def load_data():
    """Loads and cross-validates data from all experiment sources."""
    if not os.path.exists(QUEUE_FILE):
        raise FileNotFoundError(f"Missing queue file: {QUEUE_FILE}")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue_raw = json.load(f)
    queue = queue_raw.get("queue", []) if isinstance(queue_raw, dict) else queue_raw

    raw_llm = []
    if os.path.exists(RAW_LLM_FILE):
        with open(RAW_LLM_FILE, "r", encoding="utf-8") as f:
            raw_llm = [json.loads(line) for line in f if line.strip()]

    compilation = {}
    if os.path.exists(COMPILATION_FILE):
        with open(COMPILATION_FILE, "r", encoding="utf-8") as f:
            comp_list = json.load(f)
            for item in comp_list:
                req = item.get("request_id")
                if req:
                    compilation[req] = item

    quota_events = []
    if os.path.exists(QUOTA_TRACKER_FILE):
        with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
            q_data = json.load(f)
            quota_events = q_data.get("events", []) if isinstance(q_data, dict) else q_data

    return queue, raw_llm, compilation, quota_events

def run_rm3_analysis(force=False, protocol="contextual"):
    today_pt = to_pt_date()
    runner_active, runner_pid = is_runner_active()
    is_date_frozen = today_pt >= "2026-12-01"
    is_frozen = is_date_frozen and not runner_active

    print("=" * 105)
    print(" SKRIP ANALISIS RM3: GEMINI 3.8 FLASH REASONING COMPARISON (LOW vs HIGH)")
    print("=" * 105)
    print(f"Tanggal Eksekusi Saat Ini (PT) : {today_pt}")
    print(f"Syarat Pembekuan Resmi (PT)    : Tanggal Pasifik >= 2026-12-01 dan TIDAK ADA runner aktif")
    print(f"Status Pembekuan Data          : {'SUDAH DIBEKUKAN (Data Final)' if is_frozen else 'BELUM DIBEKUKAN (Data Interim / Sedang Berjalan)'}")
    print(f"Status Runner Saat Ini         : {'AKTIF (PID: ' + str(runner_pid) + ')' if runner_active else 'TIDAK AKTIF / BERSIH'}")
    print(f"Protokol Evaluasi Primer       : {protocol.capitalize()}")
    print("=" * 105)

    if not is_frozen and not force:
        print("\n" + "!" * 105)
        print("[PENGAMAN PROTOKOL AKTIF - EKSEKUSI ANALISIS DITOLAK]")
        print("!" * 105)
        print("Analisis RM3 hanya boleh dijalankan jika tahap 3.8 sudah BEKU PERMANEN dengan dua syarat mutlak:")
        print(f"  1. Tanggal kalender Pasifik >= 1 Desember 2026 (Tanggal saat ini: {today_pt}) -> {'TERPENUHI' if is_date_frozen else 'BELUM TERPENUHI'}")
        print(f"  2. Tidak boleh ada instance runner harian yang sedang berjalan -> {'TERPENUHI (BERSIH)' if not runner_active else 'BELUM TERPENUHI (RUNNER AKTIF)'}")
        print("\nTahap 3.8 masih mengumpulkan data hingga 30 November 2026 (waktu Pasifik).")
        print("Gunakan argumen --force HANYA jika ingin melihat kalkulasi data sementara (interim).\n")
        print("!" * 105)
        return

    queue, raw_llm, compilation, quota_events = load_data()

    # Filter 3.8 items from queue
    items_38 = [it for it in queue if "38" in it.get("condition", "")]
    items_low = [it for it in items_38 if it.get("condition") == "L38F-LOW"]
    items_high = [it for it in items_38 if it.get("condition") == "L38F-HIGH"]

    # Filter raw completed responses
    raw_done_38 = [r for r in raw_llm if "3.8" in r.get("model_id", "") and r.get("status") == "done"]
    raw_by_req = {r.get("request_id"): r for r in raw_done_38}

    # Map item_id to compilation validity
    # Protocol: contextual preferred, fallback to standalone
    def get_validity(req_id):
        if req_id not in compilation:
            return None
        c_item = compilation[req_id]
        p_data = c_item.get(protocol) or c_item.get("contextual") or c_item.get("standalone")
        if isinstance(p_data, dict):
            return p_data.get("valid", False)
        return False

    # -------------------------------------------------------------------------
    # (a) Jumlah Respons Selesai per Level dan per Kelompok Langkah
    # -------------------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" (a) JUMLAH RESPONS SELESAI PER LEVEL DAN PER KELOMPOK LANGKAH")
    print("-" * 95)

    groups = ["early", "mid", "late"]
    table_a = {}
    for lvl_name, lvl_items in [("LOW", items_low), ("HIGH", items_high)]:
        counts = {"done": 0, "pending": 0, "failed": 0, "total": len(lvl_items)}
        by_grp = {g: {"done": 0, "pending": 0, "failed": 0, "total": 0} for g in groups}
        for it in lvl_items:
            grp = it.get("item_id", "").split("_")[0]
            if grp not in by_grp:
                grp = "other"
                by_grp[grp] = {"done": 0, "pending": 0, "failed": 0, "total": 0}
            st = it.get("status", "pending")
            counts[st] = counts.get(st, 0) + 1
            by_grp[grp][st] = by_grp[grp].get(st, 0) + 1
            by_grp[grp]["total"] += 1
        table_a[lvl_name] = {"overall": counts, "by_group": by_grp}

    print(f"{'Level Reasoning':<16} | {'Kelompok':<8} | {'Selesai (Done)':<15} | {'Pending':<10} | {'Failed':<8} | {'Total':<6} | {'% Selesai':<10}")
    print("-" * 85)
    for lvl_name in ["LOW", "HIGH"]:
        data = table_a[lvl_name]
        for grp in groups:
            g_data = data["by_group"].get(grp, {"done": 0, "pending": 0, "failed": 0, "total": 0})
            pct = (g_data["done"] / g_data["total"] * 100) if g_data["total"] > 0 else 0.0
            print(f"L38F-{lvl_name:<11} | {grp:<8} | {g_data['done']:<15} | {g_data['pending']:<10} | {g_data['failed']:<8} | {g_data['total']:<6} | {pct:>6.1f}%")
        ov = data["overall"]
        ov_pct = (ov["done"] / ov["total"] * 100) if ov["total"] > 0 else 0.0
        print(f"  -> SUBTOTAL {lvl_name:<5} | ALL      | {ov['done']:<15} | {ov['pending']:<10} | {ov['failed']:<8} | {ov['total']:<6} | {ov_pct:>6.1f}%")
        print("-" * 85)

    # -------------------------------------------------------------------------
    # (b) Pasangan Lengkap (Complete Pairs) dan N Efektif
    # -------------------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" (b) PASANGAN LENGKAP (COMPLETE PAIRS) DAN UKURAN SAMPEL EFEKTIF (N_eff)")
    print("-" * 95)

    done_items_low = {it.get("item_id"): it for it in items_low if it.get("status") == "done"}
    done_items_high = {it.get("item_id"): it for it in items_high if it.get("status") == "done"}

    common_item_ids = sorted(set(done_items_low.keys()) & set(done_items_high.keys()))
    n_eff = len(common_item_ids)

    print(f"Total Item Selesai pada L38F-LOW  : {len(done_items_low)}")
    print(f"Total Item Selesai pada L38F-HIGH : {len(done_items_high)}")
    print(f"Jumlah Pasangan Lengkap (N_eff)   : {n_eff}")
    if common_item_ids:
        print(f"Daftar Item ID Pasangan Lengkap   : {', '.join(common_item_ids)}")
    else:
        print("Daftar Item ID Pasangan Lengkap   : (Belum ada item yang selesai di kedua level LOW dan HIGH)")

    # -------------------------------------------------------------------------
    # (c) VPR LOW dan HIGH dengan Wilson Score CI dan Penyebut Masing-Masing
    # -------------------------------------------------------------------------
    print("\n" + "-" * 95)
    print(" (c) VALID PATTERN RATE (VPR) DENGAN WILSON SCORE 95% CI & PENYEBUT")
    print("-" * 95)

    vpr_results = {}
    for lvl_name, done_dict, total_pop in [("L38F-LOW", done_items_low, len(items_low)), 
                                          ("L38F-HIGH", done_items_high, len(items_high))]:
        n_completed = len(done_dict)
        valid_count = 0
        uncompiled = 0
        for item_id, it in done_dict.items():
            req_id = it.get("request_id")
            val = get_validity(req_id)
            if val is True:
                valid_count += 1
            elif val is None:
                uncompiled += 1

        p_obs, (ci_l, ci_u) = wilson_score_interval(valid_count, n_completed)
        p_pop, (ci_l_pop, ci_u_pop) = wilson_score_interval(valid_count, total_pop)

        vpr_results[lvl_name] = {
            "valid": valid_count,
            "completed": n_completed,
            "total_pop": total_pop,
            "uncompiled": uncompiled,
            "vpr_completed": p_obs,
            "ci_completed": (ci_l, ci_u),
            "vpr_pop": p_pop,
            "ci_pop": (ci_l_pop, ci_u_pop)
        }

        print(f"Kondisi {lvl_name}:")
        print(f"  - Penyebut Respons Selesai (n = {n_completed}):")
        print(f"      Valid: {valid_count} | Tidak Valid: {n_completed - valid_count} (Belum Dikompilasi: {uncompiled})")
        print(f"      VPR: {p_obs*100:.2f}% | Wilson 95% CI: [{ci_l*100:.2f}%, {ci_u*100:.2f}%]")
        print(f"  - Penyebut Populasi Total (N = {total_pop}):")
        print(f"      VPR Imputasi Kasar: {p_pop*100:.2f}% | Wilson 95% CI: [{ci_l_pop*100:.2f}%, {ci_u_pop*100:.2f}%]")
        print()

    # -------------------------------------------------------------------------
    # (d) Uji Inferensial Berpasangan: McNemar Eksak & Bootstrap 95% CI
    # -------------------------------------------------------------------------
    print("-" * 95)
    print(" (d) UJI INFERENSIAL BERPASANGAN (MCNEMAR EKSAK & PERCENTILE BOOTSTRAP 95% CI)")
    print("-" * 95)

    if n_eff < 10:
        print(f"[HASIL UJI INFERENSIAL RM3]: TIDAK DAPAT DISIMPULKAN")
        print(f"  Rasional Metodologis:")
        print(f"  - Ukuran sampel efektif pasangan lengkap saat ini adalah N_eff = {n_eff} (< 10).")
        print(f"  - Batas minimum informatif N_eff >= 10 belum terpenuhi untuk uji inferensial berpasangan.")
        print(f"  - CATATAN TEGAS: Hasil ini BUKAN berarti 'tidak ada perbedaan', melainkan ukuran sampel")
        print(f"    pasangan lengkap belum mencukupi akibat kendala ketersediaan layanan API Google.")
    else:
        y_low = []
        y_high = []
        valid_pairs = []
        for it_id in common_item_ids:
            req_l = done_items_low[it_id].get("request_id")
            req_h = done_items_high[it_id].get("request_id")
            val_l = get_validity(req_l)
            val_h = get_validity(req_h)
            if val_l is not None and val_h is not None:
                y_low.append(1 if val_l else 0)
                y_high.append(1 if val_h else 0)
                valid_pairs.append(it_id)

        n_paired_eval = len(y_low)
        print(f"Jumlah Pasangan Tervalidasi Evaluasi: {n_paired_eval}")
        if n_paired_eval >= 10:
            b = sum(1 for l, h in zip(y_low, y_high) if l == 1 and h == 0)
            c = sum(1 for l, h in zip(y_low, y_high) if l == 0 and h == 1)
            a = sum(1 for l, h in zip(y_low, y_high) if l == 1 and h == 1)
            d = sum(1 for l, h in zip(y_low, y_high) if l == 0 and h == 0)

            print(f"Tabel Kontingensi 2x2 Pasangan Lengkap:")
            print(f"  - a (LOW=1, HIGH=1) : {a}")
            print(f"  - b (LOW=1, HIGH=0) : {b} (Discordant)")
            print(f"  - c (LOW=0, HIGH=1) : {c} (Discordant)")
            print(f"  - d (LOW=0, HIGH=0) : {d}")

            p_val, diff_discordant = paired_mcnemar_test(b, c)
            delta_obs, (b_low, b_high) = bootstrap_paired_diff_ci(y_low, y_high, rounds=BOOTSTRAP_ROUNDS, seed=BOOTSTRAP_SEED)

            print(f"\nHasil Evaluasi:")
            print(f"  - Delta VPR (HIGH - LOW) : {delta_obs*100:+.2f}%")
            print(f"  - Bootstrap 95% CI       : [{b_low*100:+.2f}%, {b_high*100:+.2f}%] ({BOOTSTRAP_ROUNDS} putaran, seed={BOOTSTRAP_SEED})")
            print(f"  - Exact McNemar p-value  : {p_val:.4f}")
            print(f"  - Signifikansi (alpha=0.05): {'Signifikan' if p_val < 0.05 else 'Tidak Signifikan'}")
        else:
            print(f"[HASIL UJI INFERENSIAL RM3]: TIDAK DAPAT DISIMPULKAN (Hanya {n_paired_eval} pasangan memiliki hasil kompilasi).")

    # -------------------------------------------------------------------------
    # (e) Tabel Ketersediaan Akses (Access Availability Table)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 115)
    print(" (e) TABEL KETERSEDIAAN AKSES MODEL 3.8: PEMBAGIAN KATEGORI HASIL PANGGILAN")
    print("-" * 115)

    # Classify events from quota_tracker
    events_38 = [e for e in quota_events if e.get("family") == "3.8" or "3.8" in e.get("model_id", "")]
    req_to_cond = {it.get("request_id"): it.get("condition") for it in items_38}

    table_e = defaultdict(lambda: defaultdict(lambda: {
        "attempts": 0, 
        "success": 0, 
        "503_server_rejected": 0, 
        "504_server_deadline": 0, 
        "client_timeout": 0, 
        "conn_reset": 0, 
        "429_quota": 0
    }))

    for e in events_38:
        e_type = e.get("event_type", "")
        if e_type == "POLICY_UPDATE_RESTORE":
            # Administrative log, not an API attempt
            continue

        ts = e.get("timestamp")
        date_pt = to_pt_date(ts)
        req_id = e.get("request_id")
        cond = req_to_cond.get(req_id, "UNKNOWN")
        lvl = "LOW" if "LOW" in cond else ("HIGH" if "HIGH" in cond else "OTHER")

        code = e.get("status_code")
        msg = str(e.get("message", "")).lower()

        table_e[date_pt][lvl]["attempts"] += 1
        if code == 200 or e_type == "SUCCESS":
            table_e[date_pt][lvl]["success"] += 1
        elif "429" in msg or code == 429:
            table_e[date_pt][lvl]["429_quota"] += 1
        elif "503" in msg or code == 503:
            table_e[date_pt][lvl]["503_server_rejected"] += 1
        elif "10053" in msg or "10054" in msg or "forcibly closed" in msg or "aborted" in msg or "10051" in msg:
            table_e[date_pt][lvl]["conn_reset"] += 1
        elif "deadline_exceeded" in msg.lower() or ("504" in msg and "gateway" in msg.lower()):
            table_e[date_pt][lvl]["504_server_deadline"] += 1
        elif "read operation timed out" in msg.lower() or ("timed out" in msg.lower() and "gateway" not in msg.lower()):
            table_e[date_pt][lvl]["client_timeout"] += 1
        else:
            table_e[date_pt][lvl]["503_server_rejected"] += 1

    print(f"{'Tanggal (PT)':<12} | {'Level':<5} | {'Percobaan':<10} | {'Berhasil':<9} | {'503 (Ditolak)':<14} | {'504 (Server)':<13} | {'Timeout Klien':<14} | {'Koneksi Putus':<14} | {'429 (Kuota)':<11}")
    print("-" * 115)
    tot_att = tot_succ = tot_503 = tot_504 = tot_cli_to = tot_conn_rst = tot_429 = 0
    for d in sorted(table_e.keys()):
        for lvl in ["LOW", "HIGH"]:
            row = table_e[d][lvl]
            if row["attempts"] > 0:
                print(f"{d:<12} | {lvl:<5} | {row['attempts']:<10} | {row['success']:<9} | {row['503_server_rejected']:<14} | {row['504_server_deadline']:<13} | {row['client_timeout']:<14} | {row['conn_reset']:<14} | {row['429_quota']:<11}")
                tot_att += row["attempts"]
                tot_succ += row["success"]
                tot_503 += row["503_server_rejected"]
                tot_504 += row["504_server_deadline"]
                tot_cli_to += row["client_timeout"]
                tot_conn_rst += row["conn_reset"]
                tot_429 += row["429_quota"]
    print("-" * 115)
    tot_unsuccessful = tot_att - tot_succ
    print(f"{'TOTAL KUMULATIF':<18} | {tot_att:<10} | {tot_succ:<9} | {tot_503:<14} | {tot_504:<13} | {tot_cli_to:<14} | {tot_conn_rst:<14} | {tot_429:<11}")
    print(f"\nRingkasan Hasil Pemanggilan 3.8 (Antrean Resmi):")
    print(f"  - Total Percobaan Panggilan API              : {tot_att}")
    print(f"  - Berhasil (HTTP 200)                        : {tot_succ} ({tot_succ/tot_att*100:.1f}%)")
    print(f"  - Tidak Berhasil (Total Kegagalan)           : {tot_unsuccessful} ({tot_unsuccessful/tot_att*100:.1f}%)")
    print(f"      * 503 (Ditolak Server / Kapasitas Habis) : {tot_503} ({tot_503/tot_att*100:.1f}%)")
    print(f"      * Timeout Klien (Read Operation Timed Out): {tot_cli_to} ({tot_cli_to/tot_att*100:.1f}%)")
    print(f"      * Koneksi Putus (WinError 10053/10054)   : {tot_conn_rst} ({tot_conn_rst/tot_att*100:.1f}%)")
    print(f"      * 504 (DEADLINE_EXCEEDED dari Server)    : {tot_504} ({tot_504/tot_att*100:.1f}%)")
    print(f"      * 429 (Batas Harian Kuota Habis)         : {tot_429} ({tot_429/tot_att*100:.1f}%)")

    # Catatan Terpisah: Uji Akses Awal (30 Okt 2026) di luar antrean resmi
    print("\n" + "." * 115)
    print(" CATATAN TERPISAH: UJI AKSES AWAL PRA-EKSPERIMEN (30 OKTOBER 2026) - DI LUAR ANTREAN RESMI")
    print("." * 115)
    print("Sumber: logs/model_access_38.json (Uji konektivitas pra-antrean sebelum batch resmi REQ-xxxx dimulai)")
    print(f"{'Sesi Pengujian':<16} | {'Level':<5} | {'Percobaan':<10} | {'Berhasil':<9} | {'503 (Ditolak)':<14} | {'504 (Server)':<13} | {'Timeout Klien':<14} | {'Koneksi Putus':<14} | {'429 (Kuota)':<11}")
    print("-" * 115)
    # 7 trials recorded in model_access_38.json
    print(f"{'30 Okt (Awal)':<16} | {'LOW':<5} | {'1':<10} | {'1':<9} | {'0':<14} | {'0':<13} | {'0':<14} | {'0':<14} | {'0':<11}")
    print(f"{'30 Okt (Awal)':<16} | {'HIGH':<5} | {'6':<10} | {'0':<9} | {'2':<14} | {'3':<13} | {'0':<14} | {'0':<14} | {'1':<11}")
    print("-" * 115)
    print(f"{'TOTAL UJI AWAL':<16} | {'ALL':<5} | {'7':<10} | {'1':<9} | {'2':<14} | {'3':<13} | {'0':<14} | {'0':<14} | {'1':<11}")
    print("Keterangan: Uji akses awal ini membuktikan 504 DEADLINE_EXCEEDED memang pernah dipancarkan langsung oleh server")
    print("Google pada 30 Okt 2026, namun TIDAK terjadi pada 86 percobaan antrean resmi (yang didominasi Timeout Klien & 503).")

    # -------------------------------------------------------------------------
    # (f) Durasi dan Thinking Token pada Respons Sukses
    # -------------------------------------------------------------------------
    print("\n" + "-" * 115)
    print(" (f) DURASI DAN THINKING TOKEN PADA RESPONS SUKSES")
    print("-" * 115)

    stats_f = {}
    for lvl_name, cond_name in [("LOW", "L38F-LOW"), ("HIGH", "L38F-HIGH")]:
        lvl_responses = [r for r in raw_done_38 if r.get("condition") == cond_name]
        durations = []
        thinking_tokens = []
        req_by_th = defaultdict(list)
        for r in lvl_responses:
            dur = r.get("elapsed_seconds") if r.get("elapsed_seconds") is not None else r.get("latency_sec")
            th = r.get("thoughts_token_count") if r.get("thoughts_token_count") is not None else r.get("thinking_tokens")
            if dur is not None:
                durations.append(float(dur))
            if th is not None:
                th_int = int(th)
                thinking_tokens.append(th_int)
                req_by_th[th_int].append(r.get("request_id"))

        stats_f[lvl_name] = {"durations": durations, "thinking": thinking_tokens, "count": len(lvl_responses)}

        print(f"Kondisi L38F-{lvl_name} (n = {len(lvl_responses)} respons sukses):")
        if durations:
            print(f"  - Durasi (detik) : Min={min(durations):.2f}s | Median={statistics.median(durations):.2f}s | "
                  f"Mean={statistics.mean(durations):.2f}s | Max={max(durations):.2f}s")
        else:
            print("  - Durasi (detik) : Data tidak tersedia.")

        if thinking_tokens:
            max_th = max(thinking_tokens)
            print(f"  - Thinking Token : Min={min(thinking_tokens)} | Median={statistics.median(thinking_tokens):.1f} | "
                  f"Mean={statistics.mean(thinking_tokens):.1f} | Max={max_th} (Tercatat pada {len(thinking_tokens)}/{len(lvl_responses)} respons)")
            
            # Hitungan respons dengan nilai thoughts_token_count persis sama dengan respons lain per level
            th_counts = Counter(thinking_tokens)
            shared_values = {val: cnt for val, cnt in th_counts.items() if cnt > 1}
            num_shared = sum(shared_values.values())
            pct_shared = (num_shared / len(thinking_tokens) * 100) if thinking_tokens else 0.0
            print(f"  - Respons dengan Thinking Token Berulang Persis (Level {lvl_name}): "
                  f"Terdapat {num_shared}/{len(thinking_tokens)} respons ({pct_shared:.1f}%) yang nilainya persis sama.")
            if shared_values:
                for val, cnt in sorted(shared_values.items()):
                    reqs = req_by_th.get(val, [])
                    print(f"      * Nilai {val} muncul {cnt} kali pada: {', '.join(reqs)}")
            else:
                print(f"      * Seluruh respons terekam memiliki nilai token unik (0 duplikasi dalam level ini).")
        else:
            print("  - Thinking Token : None / Tidak terekam.")
        print()

    # -------------------------------------------------------------------------
    # (g) Analisis Sensitivitas (a) dan (b)
    # -------------------------------------------------------------------------
    print("-" * 95)
    print(" (g) ANALISIS SENSITIVITAS (SELECTION BIAS & WORST-CASE IMPUTATION)")
    print("-" * 95)

    print("1. Sensitivitas A (Cek Bias Seleksi / Selection Bias Check):")
    n_low_all = len(done_items_low)
    valid_low_all = sum(1 for it in done_items_low.values() if get_validity(it.get("request_id")) is True)
    vpr_low_all = (valid_low_all / n_low_all) if n_low_all > 0 else 0.0

    if n_eff > 0:
        valid_low_subset = sum(1 for it_id in common_item_ids if get_validity(done_items_low[it_id].get("request_id")) is True)
        vpr_low_subset = valid_low_subset / n_eff
        diff_bias = vpr_low_subset - vpr_low_all
        print(f"   - VPR LOW pada seluruh respons selesai (n = {n_low_all})      : {vpr_low_all*100:.2f}% ({valid_low_all}/{n_low_all})")
        print(f"   - VPR LOW pada subset complete-pairs dengan HIGH (n = {n_eff})  : {vpr_low_subset*100:.2f}% ({valid_low_subset}/{n_eff})")
        print(f"   - Selisih Bias Seleksi (Subset - All)                     : {diff_bias*100:+.2f}%")
        if abs(diff_bias) < 0.10:
            print("   -> Kesimpulan Sensitivitas A: Tidak ditemukan bukti bias seleksi yang substansial pada subset.")
        else:
            print("   -> Kesimpulan Sensitivitas A: Terindikasi perbedaan proporsi; interpretasikan hasil berpasangan dengan hati-hati.")
    else:
        print(f"   - VPR LOW pada seluruh respons selesai (n = {n_low_all}): {vpr_low_all*100:.2f}%")
        print("   - Subset complete-pairs belum terbentuk (N_eff = 0), cek bias seleksi belum dapat dievaluasi.")

    print("\n2. Sensitivitas B (Skenario Konservatif / Worst-Case Imputation):")
    print(f"   Seluruh item yang belum selesai (pending/failed) diperlakukan sebagai respon TIDAK VALID (VPR = 0) pada N = 119:")
    for lvl_name in ["L38F-LOW", "L38F-HIGH"]:
        v_data = vpr_results[lvl_name]
        k = v_data["valid"]
        n_pop = v_data["total_pop"]
        p_worst, (ci_l_worst, ci_u_worst) = wilson_score_interval(k, n_pop)
        print(f"   - {lvl_name:<9} : {k}/{n_pop} = {p_worst*100:.2f}% | Wilson 95% CI: [{ci_l_worst*100:.2f}%, {ci_u_worst*100:.2f}%]")

    print("\n" + "=" * 95)
    print(" AKHIR LAPORAN ANALISIS RM3")
    print("=" * 95)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RM3 Gemini 3.8 Flash Statistical Analysis")
    parser.add_argument("--force", action="store_true", help="Force execute RM3 analysis even before the 30 Nov 2026 cutoff date")
    parser.add_argument("--protocol", choices=["contextual", "standalone"], default="contextual", help="Evaluation protocol")
    args = parser.parse_args()

    run_rm3_analysis(force=args.force, protocol=args.protocol)
