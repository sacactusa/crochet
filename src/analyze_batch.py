import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime

def analyze():
    # Load raw/llm.jsonl
    llm_records = []
    with open('raw/llm.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                llm_records.append(json.loads(line))

    # Load queue
    with open('data/experiment_queue.json', 'r', encoding='utf-8') as f:
        queue_data = json.load(f)
    queue = queue_data['queue']

    # Load quota tracker
    with open('logs/quota_tracker.json', 'r', encoding='utf-8') as f:
        quota = json.load(f)
    events = quota.get('events', [])

    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. New done today per model
    done_today_by_model = Counter()
    for r in llm_records:
        comp_at = r.get('completed_at') or r.get('timestamp') or ''
        if comp_at.startswith(today_str):
            done_today_by_model[r.get('model_id')] += 1

    print(f"=== 1. NEW DONE TODAY ({today_str}) ===")
    for m, c in sorted(done_today_by_model.items()):
        print(f"  {m}: {c}")
    print(f"  Total done today: {sum(done_today_by_model.values())}")
    print(f"  Total done cumulative: {len(llm_records)}")

    # 2. Complete Dashboard
    status_by_cond = defaultdict(Counter)
    for item in queue:
        status_by_cond[item['condition']][item['status']] += 1

    print("\n=== 2. DASHBOARD PER KONDISI ===")
    cond_order = ['L25L-OFF', 'L25L-ON', 'L25F-OFF', 'L25F-ON', 'L38F-LOW', 'L38F-HIGH']
    for c in cond_order:
        st = status_by_cond[c]
        d = st['done']
        p = st['pending']
        f = st['failed']
        tot = d + p + f
        pct = (d / tot * 100) if tot > 0 else 0
        print(f"  {c:9s} | Done: {d:3d} ({pct:5.1f}%) | Pending: {p:3d} | Failed: {f:2d} | Total: {tot}")

    # Errors per model in tracker
    err_429 = Counter()
    err_503 = Counter()
    err_504 = Counter()
    err_other = Counter()
    attempts_by_cond = Counter()
    errors_by_cond = Counter()

    for ev in events:
        m = ev.get('model_id', 'unknown')
        code = ev.get('status_code')
        etype = ev.get('event_type')
        if code == 429:
            err_429[m] += 1
        elif code == 503:
            err_503[m] += 1
        elif code == 504:
            err_504[m] += 1
        elif etype in ('ERROR', 'FAILED', 'RETRY_EXHAUSTED', 'CLIENT_TIMEOUT'):
            err_other[m] += 1

    print("\n=== ERRORS PER MODEL (CUMULATIVE) ===")
    all_models = sorted(set(list(err_429.keys()) + list(err_503.keys()) + list(err_504.keys()) + list(err_other.keys())))
    for m in all_models:
        print(f"  {m}: 429={err_429[m]}, 503={err_503[m]}, 504={err_504[m]}, other={err_other[m]}")

    # 3.8 attempts and errors for LOW vs HIGH
    # Let's inspect queue items for 3.8
    low_attempts = 0
    low_errors = 0
    high_attempts = 0
    high_errors = 0

    for item in queue:
        if item.get('family') == '3.8':
            c = item.get('condition')
            att = item.get('attempts', 0)
            errs = len(item.get('error_history', []))
            if c == 'L38F-LOW':
                low_attempts += att
                low_errors += errs
            elif c == 'L38F-HIGH':
                high_attempts += att
                high_errors += errs

    print("\n=== 3.8 ERROR RATE PER ATTEMPT ===")
    low_rate = (low_errors / low_attempts * 100) if low_attempts > 0 else 0
    high_rate = (high_errors / high_attempts * 100) if high_attempts > 0 else 0
    print(f"  L38F-LOW : {low_errors} errors / {low_attempts} attempts = {low_rate:.1f}% error rate")
    print(f"  L38F-HIGH: {high_errors} errors / {high_attempts} attempts = {high_rate:.1f}% error rate")

    # Duration for 3.8
    # Success durations from raw/llm.jsonl
    dur_38_success = []
    finish_reasons = Counter()
    max_thinking_by_cond = Counter()

    for r in llm_records:
        cond = r.get('condition', '')
        fr = str(r.get('finish_reason', 'UNKNOWN'))
        finish_reasons[fr] += 1
        th = r.get('thinking_token_count') or r.get('thoughts_token_count')
        if th is not None:
            if th > max_thinking_by_cond[cond]:
                max_thinking_by_cond[cond] = th
        if r.get('family') == '3.8' and r.get('status') == 'done':
            lat = r.get('elapsed_seconds')
            if lat:
                dur_38_success.append(lat)

    print("\n=== 3.8 SUCCESS DURATIONS (SECONDS) ===")
    if dur_38_success:
        print(f"  Count: {len(dur_38_success)}")
        print(f"  Min   : {min(dur_38_success):.2f}s")
        print(f"  Median: {statistics.median(dur_38_success):.2f}s")
        print(f"  Max   : {max(dur_38_success):.2f}s")
    else:
        print("  None")

    # Hanging calls (>600s) from error history or events
    hanging_events = []
    for ev in events:
        if ev.get('family') == '3.8':
            # check duration or message
            msg = str(ev.get('message', ''))
            lat = ev.get('duration_sec') or 0
            if lat > 600 or 'timeout' in msg.lower() or '10054' in msg.lower():
                hanging_events.append(ev)

    print(f"\n=== 3.8 HANGING / LONG CALLS (>600s or timeouts/drops) ===")
    print(f"  Total long/hanging events: {len(hanging_events)}")

    print("\n=== THINKING TOKENS HIGHEST PER COND ===")
    for c in cond_order:
        print(f"  {c:9s}: max thinking tokens = {max_thinking_by_cond[c]}")

    print("\n=== FINISH REASONS (ALL LLM RECORDS) ===")
    for fr, cnt in finish_reasons.items():
        print(f"  {fr}: {cnt}")

    failed_items = [x for x in queue if x['status'] == 'failed']
    print(f"\n=== FAILED ITEMS (DATA HILANG) ===")
    print(f"  Total failed: {len(failed_items)}")
    for fi in failed_items:
        print(f"  {fi['request_id']} | {fi['item_id']} | {fi['condition']} | attempts={fi.get('attempts')} | days={fi.get('attempt_days')}")

if __name__ == '__main__':
    analyze()
