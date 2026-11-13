import json
from datetime import datetime

# 1. Update data/experiment_queue.json
with open("data/experiment_queue.json", "r", encoding="utf-8") as f:
    q_data = json.load(f)

for item in q_data["queue"]:
    if item["request_id"] == "REQ-0002":
        item["status"] = "pending"
        item["completed_at"] = None
        item["error_history"].append({
            "timestamp": datetime.now().isoformat(),
            "action": "RESTORED_TO_PENDING",
            "reason": "Policy update per user instruction: max 1 retry per day, 3 attempts across 3 distinct days required for failure."
        })
        print(f"Restored REQ-0002 to pending.")

    if item["request_id"] == "REQ-0003":
        item["status"] = "pending"
        item["completed_at"] = None
        print(f"Confirmed REQ-0003 status: {item['status']}")

with open("data/experiment_queue.json", "w", encoding="utf-8") as f:
    json.dump(q_data, f, indent=2, ensure_ascii=False)

# 2. Check raw/llm.jsonl: If REQ-0002 was appended as 'failed', mark it in log or append-only note
raw_lines = [json.loads(l) for l in open("raw/llm.jsonl", "r", encoding="utf-8")]
failed_records = [r for r in raw_lines if r.get("status") == "failed"]
print(f"Failed records in raw/llm.jsonl: {len(failed_records)}")
for fr in failed_records:
    print(f"  Failed record: {fr['request_id']} | {fr['item_id']} | {fr['condition']}")

# Add an audit note to logs/quota_tracker.json
with open("logs/quota_tracker.json", "r", encoding="utf-8") as f:
    tracker = json.load(f)

tracker["events"].append({
    "timestamp": datetime.now().isoformat(),
    "family": "3.8",
    "model_id": "gemini-3.8-flash",
    "request_id": "REQ-0002",
    "event_type": "POLICY_UPDATE_RESTORE",
    "status_code": 200,
    "message": "REQ-0002 restored from failed to pending per multi-day retry policy."
})

with open("logs/quota_tracker.json", "w", encoding="utf-8") as f:
    json.dump(tracker, f, indent=2, ensure_ascii=False)

print("Policy update applied cleanly.")

