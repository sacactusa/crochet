import json

# Load raw/llm.jsonl
with open("raw/llm.jsonl", "r", encoding="utf-8") as f:
    raw_lines = [json.loads(line) for line in f if line.strip()]

done_requests = {}
for r in raw_lines:
    if r.get("status") == "done":
        done_requests[r["request_id"]] = r

print(f"Total done requests in raw/llm.jsonl: {len(done_requests)}")

# Load queue
with open("data/experiment_queue.json", "r", encoding="utf-8") as f:
    queue_data = json.load(f)

synced_count = 0
for item in queue_data["queue"]:
    req_id = item["request_id"]
    if req_id in done_requests:
        raw_rec = done_requests[req_id]
        if item["status"] != "done":
            item["status"] = "done"
            item["completed_at"] = raw_rec.get("timestamp")
            synced_count += 1

print(f"Newly synced items from raw to queue: {synced_count}")
total_q_done = sum(1 for e in queue_data["queue"] if e["status"] == "done")
total_q_pend = sum(1 for e in queue_data["queue"] if e["status"] == "pending")
total_q_fail = sum(1 for e in queue_data["queue"] if e["status"] == "failed")
print(f"Queue status after sync: Done={total_q_done}, Pending={total_q_pend}, Failed={total_q_fail}")

with open("data/experiment_queue.json", "w", encoding="utf-8") as f:
    json.dump(queue_data, f, indent=2, ensure_ascii=False)

print("Synchronized data/experiment_queue.json with raw/llm.jsonl successfully.")

