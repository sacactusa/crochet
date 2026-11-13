import json

print("=== AUDIT KUOTA GEMINI-3.8-FLASH ===")

# Day 1: logs/model_access_38.json
with open("logs/model_access_38.json", "r", encoding="utf-8") as f:
    log_38 = json.load(f)

trials_day1 = log_38.get("trials", [])
print(f"Day 1 (2026-10-30) Trials in logs/model_access_38.json: {len(trials_day1)}")
for idx, t in enumerate(trials_day1, 1):
    print(f"  [{idx}] {t.get('timestamp')} | level={t.get('thinking_level')} | status={t.get('status')} | http={t.get('http_status')} | err={str(t.get('error_raw'))[:80]}")

# Day 2 (today): logs/quota_tracker.json and daily_execution.log
with open("logs/quota_tracker.json", "r", encoding="utf-8") as f:
    tracker = json.load(f)

events_38 = [e for e in tracker.get("events", []) if e.get("family") == "3.8"]
print(f"\nDay 2 (2026-10-31) Events in logs/quota_tracker.json: {len(events_38)}")
for idx, e in enumerate(events_38, 1):
    print(f"  [{idx}] {e.get('timestamp')} | req={e.get('request_id')} | type={e.get('event_type')} | code={e.get('status_code')} | msg={e.get('message')[:80]}")

