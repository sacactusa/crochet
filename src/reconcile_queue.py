"""
Reconciles data/experiment_queue.json with raw/llm.jsonl.
Ensures that all successfully recorded executions in raw/llm.jsonl
are reflected with status='done' in data/experiment_queue.json.
"""

import json
import os
import shutil
from datetime import datetime

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "experiment_queue.json")
RAW_PATH = os.path.join(os.path.dirname(__file__), "..", "raw", "llm.jsonl")

def reconcile():
    print(f"Reconciling {QUEUE_PATH} with {RAW_PATH}...")
    
    if not os.path.exists(RAW_PATH):
        print(f"Error: {RAW_PATH} does not exist.")
        return
    if not os.path.exists(QUEUE_PATH):
        print(f"Error: {QUEUE_PATH} does not exist.")
        return

    # 1. Read raw LLM logs
    raw_done = {}
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            req_id = rec.get("request_id")
            if rec.get("status") == "done":
                raw_done[req_id] = rec

    print(f"Found {len(raw_done)} unique 'done' requests in raw/llm.jsonl.")

    # 2. Read experiment queue
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    entries = q_data.get("queue", [])
    updated_count = 0

    for entry in entries:
        req_id = entry.get("request_id")
        if req_id in raw_done:
            if entry.get("status") != "done":
                entry["status"] = "done"
                entry["completed_at"] = raw_done[req_id].get("timestamp")
                entry["attempts"] = max(entry.get("attempts", 0), raw_done[req_id].get("attempts", 1))
                entry_dates = entry.setdefault("attempt_dates", [])
                ts = raw_done[req_id].get("timestamp")
                if ts:
                    d_str = ts.split("T")[0]
                    if d_str not in entry_dates:
                        entry_dates.append(d_str)
                updated_count += 1

    print(f"Reconciled {updated_count} entries to 'done'.")

    # 3. Write back atomically
    tmp_path = QUEUE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(q_data, f, indent=2)
    shutil.move(tmp_path, QUEUE_PATH)
    print("Successfully saved reconciled queue.")

    # 4. Summary counts
    from collections import Counter
    c = Counter(e["status"] for e in entries)
    print(f"Queue status summary: {dict(c)}")

if __name__ == "__main__":
    reconcile()

