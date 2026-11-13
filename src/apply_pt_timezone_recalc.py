#!/usr/bin/env python3
"""
apply_pt_timezone_recalc.py

Recalculates all attempt_dates in data/experiment_queue.json to Pacific Time (America/Los_Angeles)
based on authoritative event timestamps in logs/quota_tracker.json.
Suspends marking any item as 'failed' per researcher instruction on 4 Nov 2026.
REQ-0003 is preserved as 'failed' with explicit note of following the old rule.
"""

import json
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

QUEUE_FILE = "data/experiment_queue.json"
BACKUP_FILE = "data/experiment_queue.backup_before_pt_recalc.json"
QUOTA_TRACKER_FILE = "logs/quota_tracker.json"

TZ_WIB = ZoneInfo("Asia/Jakarta")
TZ_PT = ZoneInfo("America/Los_Angeles")

def to_pt_date(ts_str):
    if not ts_str:
        return None
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_WIB)
    return dt.astimezone(TZ_PT).strftime("%Y-%m-%d")

def run():
    print("Backing up experiment queue...")
    shutil.copy2(QUEUE_FILE, BACKUP_FILE)

    with open(QUOTA_TRACKER_FILE, "r", encoding="utf-8") as f:
        events = json.load(f).get("events", [])

    req_to_pt_dates = {}
    for ev in events:
        rid = ev.get("request_id")
        ts = ev.get("timestamp")
        if rid and ts:
            pt_d = to_pt_date(ts)
            req_to_pt_dates.setdefault(rid, []).append(pt_d)

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue_data = json.load(f)

    queue = queue_data["queue"]
    updated_count = 0

    for item in queue:
        rid = item["request_id"]
        if rid in req_to_pt_dates:
            item["attempt_dates"] = req_to_pt_dates[rid]
            updated_count += 1
        
        # Ensure status suspension:
        # Only REQ-0003 is allowed to be 'failed' per historic rule
        if item.get("family") == "3.8" and rid != "REQ-0003" and item.get("status") == "failed":
            item["status"] = "pending"
            print(f"Suspended failure for {rid}; reverted to 'pending'.")

    # Add metadata note
    queue_data.setdefault("metadata", {})["timezone_standard"] = "America/Los_Angeles (Pacific Time)"
    queue_data["metadata"]["last_pt_recalculation"] = datetime.now(TZ_PT).isoformat()

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully recalculated attempt_dates for {updated_count} items in Pacific Time.")
    print("Saved updated queue to", QUEUE_FILE)

if __name__ == "__main__":
    run()

