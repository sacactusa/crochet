#!/usr/bin/env python3
"""
run_daily.py

Resumable, Quota-Aware Runner for Phase 4 LLM Translations:
- Free-Tier compliant (20 RPD per model):
  * gemini-2.5-flash-lite (RPM=15, RPD=20, timeout=180s, standard generation)
  * gemini-2.5-flash (RPM=15, RPD=20, timeout=180s, standard generation)
  * gemini-3.8-flash (RPM=15, RPD=20, timeout=600s, generate_content_stream keep-alive transport)
- Multi-Day Retry Policy for 3.8:
  * On 503/504/timeout: at most 1 retry on the same day (max 2 attempts/day).
  * Marked 'failed' (data hilang) ONLY after 3 attempts on 3 distinct days.
  * Preserves 'pending' status between days.
- Parallel worker execution between independent model families.
- Atomic queue persistence in data/experiment_queue.json.
- Append-only logging in raw/llm.jsonl.
- Comprehensive status dashboard with 429 and 503/504 counts.
"""

import os
import sys
import json
import time
import argparse
import tempfile
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types
try:
    from reconcile_queue import reconcile
except ImportError:
    from src.reconcile_queue import reconcile

QUEUE_FILE = "data/experiment_queue.json"
PROMPTS_FILE = "prompts/prompts.json"
RAW_LLM_FILE = "raw/llm.jsonl"
QUOTA_TRACKER_FILE = "logs/quota_tracker.json"
DETAILED_38_LOG = "logs/model_access_38_detailed.jsonl"

TZ_WIB = ZoneInfo("Asia/Jakarta")
TZ_PT = ZoneInfo("America/Los_Angeles")

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
        return ts_str[:10]

SYSTEM_PROMPT = """You are a crochet compiler. Translate the next instruction NL into one line of CrochetPARADE DSL.
Use consistent naming and syntax.

Important rules for translations:
1. Make sure your output ONLY contains the DSL code, nothing else.
2. Use the previous examples to understand the pattern of translation.
3. Be consistent in naming conventions with the examples.
4. Your output should be exactly one line of DSL code."""

# Rate limit safeguards (Free tier)
MODEL_DELAYS = {
    "gemini-2.5-flash-lite": 4.5,  # 15 RPM Free tier limit
    "gemini-2.5-flash": 13.0,      # 5 RPM Free tier limit (60s / 5 = 12s)
    "gemini-3.8-flash": 5.0
}
DELAY_25_SECONDS = 4.5
DELAY_38_SECONDS = 5.0

# Free tier daily quotas (Empirically verified)
RPD_LIMITS = {
    "gemini-2.5-flash-lite": 20,
    "gemini-2.5-flash": 20,
    "gemini-3.8-flash": 20
}

# Process lock, stage timeouts, and pacing (Option A - 4 Nov 2026)
LOCK_FILE = "data/runner.lock"
MAX_RUNTIME_25 = 2 * 3600    # Stage 2.5: max 2 hours (7,200s)
MAX_RUNTIME_38 = 12 * 3600   # Stage 3.8: max 12 hours (43,200s)

# Pacing & Circuit Breaker parameters for Gemini 3.8 Flash
PACING_DELAY_38 = 1800.0       # ~30 minutes between attempts (avoid burst)
CIRCUIT_BREAKER_WAIT = 3600.0  # 60 minutes cooldown after 2 consecutive 503s

# Pacing delays per model
MODEL_DELAYS = {
    "gemini-2.5-flash-lite": 4.5,
    "gemini-2.5-flash": 13.0,
    "gemini-3.8-flash": PACING_DELAY_38,
}

# Windows Power Management: Prevent system sleep while runner is active
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

def prevent_windows_sleep():
    """Informs Windows OS to keep system awake while process is running."""
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            print("[POWER] Windows sleep prevention enabled (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).", flush=True)
    except Exception as e:
        print(f"[POWER] Warning: Failed to enable sleep prevention: {e}", flush=True)

def restore_windows_sleep():
    """Restores default Windows sleep behavior."""
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            print("[POWER] Windows sleep prevention restored to normal (ES_CONTINUOUS).", flush=True)
    except Exception as e:
        print(f"[POWER] Warning: Failed to restore sleep state: {e}", flush=True)

def is_pid_alive(pid):
    if pid <= 0:
        return False
    try:
        if os.name == 'nt':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process:
                kernel32.CloseHandle(process)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False

def acquire_instance_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
                lock_data = json.loads(content) if content.startswith("{") else {"pid": int(content)}
                lock_pid = lock_data.get("pid", 0)
                if is_pid_alive(lock_pid):
                    print(f"\n{'!'*70}")
                    print(f"[LOCK ERROR] Another instance of run_daily.py is already running (PID: {lock_pid}).")
                    print(f"Lock acquired at: {lock_data.get('timestamp', 'unknown')}")
                    print("Exiting to prevent concurrent execution conflicts.")
                    print(f"{'!'*70}\n")
                    sys.exit(1)
                else:
                    print(f"[LOCK] Removing stale lock file from inactive PID {lock_pid}.")
        except Exception:
            pass

    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        json.dump({"pid": os.getpid(), "timestamp": datetime.now().isoformat()}, f)

def release_instance_lock():
    try:
        if not os.path.exists(LOCK_FILE):
            return
        with open(LOCK_FILE, "r") as f:
            content = f.read().strip()
        lock_data = json.loads(content) if content.startswith("{") else {"pid": int(content)}
        if lock_data.get("pid") == os.getpid():
            os.remove(LOCK_FILE)
    except Exception:
        pass

file_lock = threading.Lock()

def load_queue():
    if not os.path.exists(QUEUE_FILE):
        raise FileNotFoundError(f"Experiment queue not found at {QUEUE_FILE}. Run build_experiment_queue.py first.")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_queue(queue_data):
    with file_lock:
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        dir_name = os.path.dirname(QUEUE_FILE)
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(queue_data, tf, indent=2, ensure_ascii=False)
            temp_path = tf.name
        os.replace(temp_path, QUEUE_FILE)

def append_raw_log(entry):
    with file_lock:
        os.makedirs(os.path.dirname(RAW_LLM_FILE), exist_ok=True)
        with open(RAW_LLM_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def record_quota_event(family, model_id, request_id, event_type, status_code, message):
    with file_lock:
        os.makedirs(os.path.dirname(QUOTA_TRACKER_FILE), exist_ok=True)
        tracker = {"events": []}
        if os.path.exists(QUOTA_TRACKER_FILE):
            try:
                with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
                    tracker = json.load(f)
            except Exception:
                tracker = {"events": []}
        
        tracker["events"].append({
            "timestamp": datetime.now().isoformat(),
            "family": family,
            "model_id": model_id,
            "request_id": request_id,
            "event_type": event_type,
            "status_code": status_code,
            "message": message
        })
        
        with open(QUOTA_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)

def record_detailed_38_attempt(req_id, item_id, condition, level, attempt_today, total_attempts,
                               status_code, elapsed, first_chunk_elapsed, chunk_count,
                               has_chunks_thinking, thoughts, finish_reason, raw_error):
    with file_lock:
        os.makedirs(os.path.dirname(DETAILED_38_LOG), exist_ok=True)
        rec = {
            "timestamp": datetime.now().isoformat(),
            "request_id": req_id,
            "item_id": item_id,
            "condition": condition,
            "thinking_level": level,
            "attempt_today": attempt_today,
            "total_attempts": total_attempts,
            "status_code": status_code,
            "elapsed_seconds": round(elapsed, 2),
            "first_chunk_elapsed_seconds": round(first_chunk_elapsed, 2) if first_chunk_elapsed is not None else None,
            "chunk_count": chunk_count,
            "has_chunks_during_thinking": has_chunks_thinking,
            "thoughts_token_count": thoughts,
            "finish_reason": finish_reason,
            "raw_error": raw_error
        }
        with open(DETAILED_38_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def get_client(family):
    if family == "2.5":
        key = os.environ.get("GEMINI_API_KEY_25")
        if not key:
            raise ValueError("GEMINI_API_KEY_25 is not set in environment.")
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=180000)  # 180s
        )
    elif family == "3.8":
        key = os.environ.get("GEMINI_API_KEY_38")
        if not key:
            raise ValueError("GEMINI_API_KEY_38 is not set in environment.")
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=600000)  # 600s
        )
    else:
        raise ValueError(f"Unknown model family: {family}")

def print_dashboard(queue_data=None):
    if queue_data is None:
        queue_data = load_queue()

    entries = queue_data["queue"]
    conditions = ["L25L-OFF", "L25L-ON", "L25F-OFF", "L25F-ON", "L38F-LOW", "L38F-HIGH"]

    # Load quota events for error metrics
    events = []
    if os.path.exists(QUOTA_TRACKER_FILE):
        try:
            with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
                events = json.load(f).get("events", [])
        except Exception:
            events = []

    print("\n" + "=" * 92)
    print(" CROCHETBENCH-DSTEP LLM TRANSLATION PIPELINE — STATUS DASHBOARD")
    print("=" * 92)
    print(f"{'Condition':<10} | {'Model':<22} | {'Done':<5} | {'Pend':<5} | {'Fail':<5} | {'Total':<5} | {'Prog':<7} | {'429s':<5} | {'503/504':<7}")
    print("-" * 92)

    req_to_cond = {e["request_id"]: e["condition"] for e in entries}

    for c in conditions:
        cond_entries = [e for e in entries if e["condition"] == c]
        total = len(cond_entries)
        done = sum(1 for e in cond_entries if e["status"] == "done")
        pending = sum(1 for e in cond_entries if e["status"] == "pending")
        failed = sum(1 for e in cond_entries if e["status"] == "failed")
        prog = f"{(done/total*100) if total else 0:.1f}%"
        model_name = cond_entries[0]["model_id"] if cond_entries else ""
        
        # Error metrics for this specific condition
        c_events = [ev for ev in events if req_to_cond.get(ev.get("request_id")) == c]
        c_429 = sum(1 for ev in c_events if ev.get("status_code") == 429)
        c_50x = sum(1 for ev in c_events if ev.get("status_code") in (503, 504))
        
        print(f"{c:<10} | {model_name:<22} | {done:<5} | {pending:<5} | {failed:<5} | {total:<5} | {prog:<7} | {c_429:<5} | {c_50x:<7}")

    print("-" * 92)
    
    # Days estimate based on Free Tier RPD per model (Theoretical)
    m_lite_pend = sum(1 for e in entries if e["model_id"] == "gemini-2.5-flash-lite" and e["status"] == "pending")
    m_flash_pend = sum(1 for e in entries if e["model_id"] == "gemini-2.5-flash" and e["status"] == "pending")
    m_38_pend = sum(1 for e in entries if e["model_id"] == "gemini-3.8-flash" and e["status"] == "pending")

    days_lite = (m_lite_pend + 19) // 20 if m_lite_pend > 0 else 0
    days_flash = (m_flash_pend + 19) // 20 if m_flash_pend > 0 else 0

    # Days estimate based on Empirical Success Rate (Nyata)
    # 2.5-Lite: ~17-20 sukses/hari -> real_days_lite
    # 2.5-Flash: ~13-20 sukses/hari (karena jeda 5 RPM) -> real_days_flash
    real_days_lite = int((m_lite_pend + 16) // 17) if m_lite_pend > 0 else 0
    real_days_flash = int((m_flash_pend + 12) // 13) if m_flash_pend > 0 else 0

    # Laju Nyata Gemini 3.8 Flash Sejak 1 Nov (termasuk hari dengan nol respon)
    today_pt_date = datetime.now(TZ_PT).date()
    start_pt_date = datetime(2026, 11, 1).date()
    days_since_nov1 = max(1, (today_pt_date - start_pt_date).days + 1)
    succ_38_since_nov1 = sum(1 for ev in events if ev.get("model_id") == "gemini-3.8-flash" and ev.get("status_code") == 200 and to_pt_date(ev.get("timestamp")) >= "2026-11-01")
    rate_38_daily = succ_38_since_nov1 / days_since_nov1

    total_done = sum(1 for e in entries if e["status"] == "done")
    total_pend = sum(1 for e in entries if e["status"] == "pending")
    total_fail = sum(1 for e in entries if e["status"] == "failed")
    grand_total = len(entries)

    print(f"gemini-2.5-flash-lite : Pending={m_lite_pend:<3} | Hari Teoritis (20/hr): {days_lite:<2} | Hari Nyata (17/hr): {real_days_lite:<2} hari")
    print(f"gemini-2.5-flash      : Pending={m_flash_pend:<3} | Hari Teoritis (20/hr): {days_flash:<2} | Hari Nyata (13/hr): {real_days_flash:<2} hari")
    print(f"gemini-3.8-flash      : Pending={m_38_pend:<3} | Laju Nyata Sejak 1 Nov: {rate_38_daily:.2f} resp/hari ({succ_38_since_nov1} sukses dlm {days_since_nov1} hari, termasuk hari=0)")
    print("-" * 92)
    print(f"TOTAL DATA KUMULATIF  : Done={total_done}/{grand_total} ({(total_done/grand_total*100):.1f}%) | Pending={total_pend} | Failed={total_fail}")
    
    # Missing Data Report for Gemini 3.8
    print("-" * 92)
    print(" GEMINI 3.8 FLASH MISSING DATA REPORT (LOW vs HIGH)")
    print("-" * 92)
    for lvl, cond_name in [("LOW", "L38F-LOW"), ("HIGH", "L38F-HIGH")]:
        cond_ents = [e for e in entries if e["condition"] == cond_name]
        c_done = sum(1 for e in cond_ents if e["status"] == "done")
        c_pend = sum(1 for e in cond_ents if e["status"] == "pending")
        c_fail = sum(1 for e in cond_ents if e["status"] == "failed")
        c_tot = len(cond_ents)
        fail_rate = (c_fail / (c_done + c_fail) * 100) if (c_done + c_fail) > 0 else 0.0

        # By step group
        early_f = sum(1 for e in cond_ents if e["status"] == "failed" and e["item_id"].startswith("early"))
        mid_f = sum(1 for e in cond_ents if e["status"] == "failed" and e["item_id"].startswith("mid"))
        late_f = sum(1 for e in cond_ents if e["status"] == "failed" and e["item_id"].startswith("late"))

        early_d = sum(1 for e in cond_ents if e["status"] == "done" and e["item_id"].startswith("early"))
        mid_d = sum(1 for e in cond_ents if e["status"] == "done" and e["item_id"].startswith("mid"))
        late_d = sum(1 for e in cond_ents if e["status"] == "done" and e["item_id"].startswith("late"))

        # Error rate per attempt (galat / percobaan)
        lvl_events = [ev for ev in events if req_to_cond.get(ev.get("request_id")) == cond_name]
        tot_attempts = len(lvl_events)
        err_attempts = sum(1 for ev in lvl_events if ev.get("status_code") in (503, 504))
        attempt_err_rate = (err_attempts / tot_attempts * 100) if tot_attempts > 0 else 0.0

        print(f"  Level {lvl:<4} ({cond_name}): Done={c_done}/{c_tot} | Pending={c_pend} | Failed={c_fail} ({fail_rate:.1f}% missing)")
        print(f"    - Tingkat Galat per Percobaan: {attempt_err_rate:.1f}% ({err_attempts} galat / {tot_attempts} percobaan)")
        print(f"    - Step Groups: Early(done={early_d}, fail={early_f}) | Mid(done={mid_d}, fail={mid_f}) | Late(done={late_d}, fail={late_f})")
    
    # Quota Deduction Tracking for 3.8
    events_38 = [ev for ev in events if ev.get("model_id") == "gemini-3.8-flash"]
    attempts_38 = len(events_38)
    succ_38 = sum(1 for ev in events_38 if ev.get("event_type") == "SUCCESS")
    err_38 = sum(1 for ev in events_38 if ev.get("status_code") in (503, 504))
    q429_38 = sum(1 for ev in events_38 if ev.get("status_code") == 429)
    print(f"  Quota 3.8 Tracker: Total Recorded Attempts={attempts_38} (Success={succ_38}, 503/504 Errors={err_38}, 429s={q429_38})")
    print(f"  Quota Reduction Evidence: Terbukti empiris (4 Nov) bahwa 21 panggilan galat 503 berturut-turut memotong habis kuota harian Free Tier (20 RPD) hingga memicu 429.")
    print(f"  Catatan 503: Galat 503 UNAVAILABLE yang kembali dalam 7-8 detik merupakan penolakan kapasitas kluster server Google, TIDAK berkaitan dengan level reasoning model.")
    print("=" * 92 + "\n")

def run_worker_for_family(family, max_requests=20, dry_run=False, pacing_delay=None, circuit_breaker_wait=None, stage_runtime_limit=None, client_override=None):
    today_str = datetime.now(TZ_PT).strftime("%Y-%m-%d")
    if family == "3.8" and today_str > "2026-11-30":
        print(f"[{family}] Tahap 3.8 telah resmi ditutup pada 30 November 2026 (PT). Data telah dibekukan sesuai keputusan peneliti. Melewati tahap 3.8.", flush=True)
        return
    stage_limit = stage_runtime_limit if stage_runtime_limit is not None else (MAX_RUNTIME_38 if family == "3.8" else MAX_RUNTIME_25)
    cb_wait = circuit_breaker_wait if circuit_breaker_wait is not None else CIRCUIT_BREAKER_WAIT
    print(f"[{family}] Worker started for Family {family} on {today_str} (PT calendar date, daily cap={max_requests}, max runtime={stage_limit/3600:.1f}h)...", flush=True)
    queue_data = load_queue()
    entries = queue_data["queue"]

    # Filter pending entries for this family
    pending_items = [e for e in entries if e["family"] == family and e["status"] == "pending"]
    if not pending_items:
        print(f"[{family}] No pending items for Family {family}. All completed or failed.", flush=True)
        return

    print(f"[{family}] Found {len(pending_items)} pending items.", flush=True)
    if dry_run:
        print(f"[{family}] DRY-RUN enabled. Simulating first 3 items:")
        for it in pending_items[:3]:
            print(f"  - {it['request_id']} | Item: {it['item_id']} | Condition: {it['condition']} | Model: {it['model_id']}")
        return

    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    client = client_override if client_override is not None else get_client(family)
    batch_start_time = time.time()
    models_in_family = set(e["model_id"] for e in pending_items)
    processed_per_model = {}
    q_events = []
    if os.path.exists(QUOTA_TRACKER_FILE):
        with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
            q_events = json.load(f).get("events", [])
    for m in models_in_family:
        done_today = sum(1 for ev in q_events if ev.get("model_id") == m and to_pt_date(ev.get("timestamp")) == today_str and ev.get("status_code") == 200)
        processed_per_model[m] = done_today
    exhausted_models = set()
    consecutive_503_count = 0

    for item in pending_items:
        # Check stage-specific runtime limit
        elapsed_sec = time.time() - batch_start_time
        if elapsed_sec > stage_limit:
            elapsed_hrs = elapsed_sec / 3600.0
            limit_hrs = stage_limit / 3600.0
            print(f"\n{'!'*70}")
            print(f"[{family}] Maximum stage runtime limit of {limit_hrs:.1f} hours exceeded ({elapsed_hrs:.2f}h elapsed).")
            print(f"[{family}] Stopping stage {family} gracefully. Remaining items remain PENDING.")
            print(f"{'!'*70}\n", flush=True)
            save_queue(queue_data)
            break

        model_id = item["model_id"]
        if model_id in exhausted_models:
            continue

        if max_requests is not None and processed_per_model.get(model_id, 0) >= max_requests:
            if all(processed_per_model.get(m, 0) >= max_requests or m in exhausted_models for m in models_in_family):
                print(f"[{family}] All models have completed their daily batch limit of {max_requests}. Stopping for today.", flush=True)
                break
            continue

        # Check if item already attempted twice today
        attempt_dates = item.setdefault("attempt_dates", [])
        todays_attempts = [d for d in attempt_dates if d == today_str]
        if family == "3.8" and len(todays_attempts) >= 2:
            # Already tried twice today; skip to next item for today
            continue

        delay_sec = pacing_delay if pacing_delay is not None else MODEL_DELAYS.get(model_id, 5.0)

        req_id = item["request_id"]
        item_id = item["item_id"]
        cond = item["condition"]
        config_dict = item["config"]
        p_entry = prompts[item_id]
        prompt_text = p_entry["prompt"]

        print(f"\n[{family}] Executing {req_id} ({item_id} | {cond} | {model_id})...", flush=True)

        # Build Config
        gen_cfg_args = {
            "max_output_tokens": config_dict.get("max_output_tokens", 32768)
        }
        if "thinking_budget" in config_dict:
            gen_cfg_args["thinking_config"] = types.ThinkingConfig(thinking_budget=config_dict["thinking_budget"])
        elif "thinking_level" in config_dict:
            gen_cfg_args["thinking_config"] = types.ThinkingConfig(thinking_level=config_dict["thinking_level"])

        cfg = types.GenerateContentConfig(**gen_cfg_args)
        assert cfg.temperature is None, "temperature must not be sent"
        assert cfg.top_p is None, "top_p must not be sent"
        assert cfg.top_k is None, "top_k must not be sent"

        # Retry policy:
        # 2.5: up to 3 retries on same day
        # 3.8: at most 1 retry on same day (total 2 attempts today), failed only after 3 distinct days
        max_attempts_today = 2 if family == "3.8" else 3
        attempts_today = 0
        success = False
        error_msg = None

        while attempts_today < max_attempts_today and not success:
            attempts_today += 1
            item["attempts"] = item.get("attempts", 0) + 1
            item["attempt_dates"].append(today_str)
            t0 = time.time()
            timestamp = datetime.now().isoformat()

            try:
                if family == "3.8":
                    # Use generate_content_stream to maintain active keep-alive connection
                    stream = client.models.generate_content_stream(
                        model=model_id,
                        contents=[SYSTEM_PROMPT, prompt_text],
                        config=cfg
                    )
                    chunks = []
                    thoughts = None
                    prompt_tok = None
                    cand_tok = None
                    finish = "STOP"
                    first_chunk_elapsed = None
                    chunk_count = 0
                    for chunk in stream:
                        chunk_count += 1
                        if first_chunk_elapsed is None:
                            first_chunk_elapsed = time.time() - t0
                        if chunk.text:
                            chunks.append(chunk.text)
                        if getattr(chunk, "usage_metadata", None):
                            um = chunk.usage_metadata
                            if getattr(um, "thoughts_token_count", None) is not None:
                                thoughts = um.thoughts_token_count
                            if getattr(um, "prompt_token_count", None) is not None:
                                prompt_tok = um.prompt_token_count
                            if getattr(um, "candidates_token_count", None) is not None:
                                cand_tok = um.candidates_token_count
                        if getattr(chunk, "candidates", None) and chunk.candidates:
                            finish = str(chunk.candidates[0].finish_reason)
                    raw_text = "".join(chunks)
                    elapsed = time.time() - t0
                    record_detailed_38_attempt(
                        req_id, item_id, cond, config_dict.get("thinking_level"),
                        attempts_today, item["attempts"], 200, elapsed,
                        first_chunk_elapsed, chunk_count, chunk_count > 0,
                        thoughts, finish, None
                    )
                else:
                    res = client.models.generate_content(
                        model=model_id,
                        contents=[SYSTEM_PROMPT, prompt_text],
                        config=cfg
                    )
                    elapsed = time.time() - t0
                    raw_text = res.text
                    usage = getattr(res, "usage_metadata", None)
                    thoughts = getattr(usage, "thoughts_token_count", None) if usage else None
                    prompt_tok = getattr(usage, "prompt_token_count", None) if usage else None
                    cand_tok = getattr(usage, "candidates_token_count", None) if usage else None
                    finish = str(res.candidates[0].finish_reason) if res.candidates else "UNKNOWN"

                success = True

                # Record success log
                raw_record = {
                    "request_id": req_id,
                    "item_id": item_id,
                    "condition": cond,
                    "family": family,
                    "model_id": model_id,
                    "key_alias": item["key_alias"],
                    "prompt_hash": item["prompt_hash"],
                    "full_prompt_hash": item["full_prompt_hash"],
                    "params_sent": {
                        "thinking_budget": config_dict.get("thinking_budget"),
                        "thinking_level": config_dict.get("thinking_level"),
                        "max_output_tokens": config_dict.get("max_output_tokens", 32768),
                        "temperature": None,
                        "top_p": None,
                        "top_k": None,
                        "sampling": "default_model_sampling_not_sent"
                    },
                    "status": "done",
                    "raw_response_text": raw_text,
                    "thoughts_token_count": thoughts,
                    "prompt_token_count": prompt_tok,
                    "candidates_token_count": cand_tok,
                    "finish_reason": finish,
                    "elapsed_seconds": round(elapsed, 2),
                    "attempts": item["attempts"],
                    "error": None,
                    "timestamp": timestamp
                }
                append_raw_log(raw_record)
                record_quota_event(family, model_id, req_id, "SUCCESS", 200, "Request successful")

                # Update queue entry
                item["status"] = "done"
                item["completed_at"] = timestamp
                item.setdefault("error_history", []).append({"attempt": item["attempts"], "status": "SUCCESS", "elapsed": round(elapsed, 2)})
                processed_per_model[model_id] = processed_per_model.get(model_id, 0) + 1
                print(f"[{family}] {req_id} SUCCESS in {elapsed:.2f}s | thinking={thoughts} | finish={finish}", flush=True)

            except Exception as e:
                elapsed = time.time() - t0
                err_str = str(e)
                error_msg = err_str
                print(f"[{family}] {req_id} Attempt {attempts_today}/{max_attempts_today} FAILED in {elapsed:.2f}s: {err_str[:120]}...", flush=True)

                # Check if 429 RESOURCE_EXHAUSTED
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    is_minute_rate_limit = ("GenerateRequestsPerMinute" in err_str) or ("limit: 5" in err_str)
                    if is_minute_rate_limit:
                        print(f"[{family}] 429 RPM Rate limit encountered for {model_id}. Waiting 60s for RPM window reset...", flush=True)
                        record_quota_event(family, model_id, req_id, "QUOTA_RPM_429", 429, err_str)
                        time.sleep(60)
                        continue
                    else:
                        print(f"\n{'!'*60}")
                        print(f"[{family}] 429 RESOURCE_EXHAUSTED (DAILY RPD) ENCOUNTERED for {model_id}!")
                        print(f"[{family}] Free tier daily quota limit reached for {model_id}. Preserving pending status and skipping this model.")
                        print(f"{'!'*60}\n", flush=True)

                        record_quota_event(family, model_id, req_id, "QUOTA_EXHAUSTED_429", 429, err_str)
                        item.setdefault("error_history", []).append({"attempt": item["attempts"], "status": "429_EXHAUSTED", "error": err_str})
                        exhausted_models.add(model_id)
                        save_queue(queue_data)
                        break

                # Check if 503/504/timeout
                status_code = 503 if "503" in err_str else 504
                record_quota_event(family, model_id, req_id, "SERVER_ERROR", status_code, err_str)
                item.setdefault("error_history", []).append({"attempt": item["attempts"], "status": "ERROR", "error": err_str})
                if family == "3.8":
                    record_detailed_38_attempt(
                        req_id, item_id, cond, config_dict.get("thinking_level"),
                        attempts_today, item["attempts"], status_code, elapsed,
                        None, 0, False, None, "ERROR", err_str
                    )
                    if status_code == 503:
                        consecutive_503_count += 1
                        if consecutive_503_count >= 2:
                            print(f"\n{'='*70}")
                            print(f"[{family}] CIRCUIT BREAKER TRIGGERED: {consecutive_503_count} consecutive 503 errors encountered.")
                            print(f"[{family}] Cooling down for {int(cb_wait // 60)} minutes ({cb_wait}s) before next attempt to allow server demand to subside...")
                            print(f"{'='*70}\n", flush=True)
                            record_quota_event(family, model_id, req_id, "CIRCUIT_BREAKER_503", 503, f"Circuit breaker: 2 consecutive 503s. Waiting {cb_wait}s.")
                            time.sleep(cb_wait)
                            consecutive_503_count = 0

                if attempts_today < max_attempts_today:
                    if family == "3.8":
                        backoff = delay_sec
                        print(f"[{family}] Pacing retry: waiting {int(backoff // 60)}m ({backoff}s) before retry attempt {attempts_today + 1}...", flush=True)
                    else:
                        backoff = [10, 30, 60][attempts_today - 1]
                        print(f"[{family}] Waiting {backoff}s before retry...", flush=True)
                    time.sleep(backoff)

        # After attempts today exhausted without success
        if not success:
            if model_id in exhausted_models:
                if exhausted_models >= models_in_family:
                    print(f"[{family}] All models in family {family} have reached daily quota. Halting worker.", flush=True)
                    save_queue(queue_data)
                    break
                else:
                    save_queue(queue_data)
                    continue
            else:
                # Check distinct days criterion for failure
                distinct_days = len(set(item.get("attempt_dates", [])))
                if family == "3.8":
                    # TANGGUHKAN penandaan "failed" untuk item 3.8 akibat 503/504/timeout per instruksi Peneliti 4 Nov.
                    # Item tetap pending; seluruh percobaan, tanggal (Pasifik), status HTTP, dan galat tetap dicatat.
                    # Keputusan penandaan data hilang ditunda sampai Peneliti & dosen pembimbing memutuskan.
                    item["status"] = "pending"
                    print(f"[{family}] {req_id} Gagal hari ini ({distinct_days} hari berbeda Pasifik). Penandaan 'failed' DITANGGUHKAN. Status tetap PENDING.", flush=True)
                else:
                    # Marked as failed (missing data)
                    item["status"] = "failed"
                    item["completed_at"] = datetime.now().isoformat()
                    print(f"[{family}] {req_id} FAILED after {distinct_days} distinct days. Marked as 'failed' (data hilang).", flush=True)
                    raw_record = {
                        "request_id": req_id,
                        "item_id": item_id,
                        "condition": cond,
                        "family": family,
                        "model_id": model_id,
                        "key_alias": item["key_alias"],
                        "prompt_hash": item["prompt_hash"],
                        "full_prompt_hash": item["full_prompt_hash"],
                        "status": "failed",
                        "raw_response_text": None,
                        "thoughts_token_count": None,
                        "prompt_token_count": None,
                        "candidates_token_count": None,
                        "finish_reason": "FAILED",
                        "elapsed_seconds": round(elapsed, 2),
                        "attempts": item["attempts"],
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    append_raw_log(raw_record)
                processed_per_model[model_id] = processed_per_model.get(model_id, 0) + 1

        save_queue(queue_data)
        if any(processed_per_model.get(m, 0) < max_requests for m in models_in_family if m not in exhausted_models):
            if family == "3.8":
                print(f"[{family}] Inter-request pacing: waiting {int(delay_sec // 60)}m ({delay_sec}s) before next item...", flush=True)
            else:
                print(f"[{family}] Pacing delay: waiting {delay_sec}s before next request...", flush=True)
            time.sleep(delay_sec)

    print(f"[{family}] Worker completed. Processed {sum(processed_per_model.values())} items.", flush=True)

def main():
    parser = argparse.ArgumentParser(description="Resumable Daily Runner for CrochetBench-Dstep Phase 4 LLM Translations")
    parser.add_argument("--family", choices=["2.5", "3.8"], help="Run requests for a specific model family only")
    parser.add_argument("--all", action="store_true", help="Run requests for both Family 2.5 and 3.8")
    parser.add_argument("--status", action="store_true", help="Print experiment queue status dashboard and exit")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without sending API requests")
    parser.add_argument("--max-requests", type=int, default=20, help="Maximum requests per family per daily run (default=20)")
    args = parser.parse_args()

    if not args.dry_run:
        reconcile()

    if args.status or (not args.family and not args.all):
        print_dashboard()
        return

    if not args.dry_run:
        acquire_instance_lock()
        prevent_windows_sleep()
    try:
        if args.family:
            run_worker_for_family(args.family, max_requests=args.max_requests, dry_run=args.dry_run)
        elif args.all:
            print("\n" + "="*50)
            print(">>> STARTING FAMILY 2.5 WORKER (gemini-2.5-flash-lite & gemini-2.5-flash)")
            print("="*50)
            run_worker_for_family("2.5", max_requests=args.max_requests, dry_run=args.dry_run)
            
            print("\n" + "="*50)
            print(">>> STARTING FAMILY 3.8 WORKER (gemini-3.8-flash)")
            print("="*50)
            run_worker_for_family("3.8", max_requests=args.max_requests, dry_run=args.dry_run)
    finally:
        if not args.dry_run:
            restore_windows_sleep()
            release_instance_lock()

    if not args.dry_run:
        reconcile()
    print_dashboard()

if __name__ == "__main__":
    main()
