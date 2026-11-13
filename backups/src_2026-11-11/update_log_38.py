import json

with open("logs/model_access_38.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Update classification cleanly
data["classification"] = {
    "level_low": "LAYAK",
    "level_high": "SERVER SIBUK / DEADLINE EXCEEDED & QUOTA EXHAUSTED (RPD=20)",
    "overall": "SATU LEVEL BERHASIL (LOW), SATU LEVEL GAGAL (HIGH: 503/504/429)"
}

with open("logs/model_access_38.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Updated logs/model_access_38.json")
for t in data["trials"]:
    print(f"Level {t.get('thinking_level')} Attempt {t.get('attempt')}: Status={t.get('status')} HTTP={t.get('http_status')} Elapsed={t.get('elapsed_seconds')}s")

