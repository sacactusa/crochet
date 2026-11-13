import json

raw_lines = [json.loads(l) for l in open('raw/llm.jsonl', encoding='utf-8')]
pilot_lines = [json.loads(l) for l in open('logs/pilot_25.jsonl', encoding='utf-8')]

print("=== 1. PILOT DATA (logs/pilot_25.jsonl) ===")
pilot_items = sorted(list(set(p['item_id'] for p in pilot_lines)))
print(f"Total Pilot Calls in logs/pilot_25.jsonl: {len(pilot_lines)}")
print(f"Pilot Item IDs ({len(pilot_items)} items): {pilot_items}")
for p in pilot_lines:
    print(f"  Pilot Record: {p['item_id']} | {p['condition_id']} | {p['model_id']} | {p['timestamp']}")

print("\n=== 2. RAW LLM DATA (raw/llm.jsonl) ===")
print(f"Total Records in raw/llm.jsonl: {len(raw_lines)}")
night_records = [r for r in raw_lines if r['timestamp'].startswith('2026-10-30')]
today_records = [r for r in raw_lines if r['timestamp'].startswith('2026-10-31')]
print(f"2026-10-30 (Tadi malam) records: {len(night_records)}")
print(f"2026-10-31 (Hari ini) records: {len(today_records)}")

print("\n--- 14 Records from 2026-10-30 ---")
for r in night_records:
    print(f"  {r['request_id']} | {r['item_id']} | {r['condition']} | {r['model_id']} | {r['timestamp']}")

# Check whether ANY pilot records from logs/pilot_25.jsonl were ever written to raw/llm.jsonl
pilot_hashes = set(p['prompt_hash'] for p in pilot_lines)
raw_hashes = set(r['prompt_hash'] for r in raw_lines)
raw_pilot_overlap = [r for r in raw_lines if r.get('pilot') is True]
print(f"\nExplicit pilot records in raw/llm.jsonl (with pilot=True): {len(raw_pilot_overlap)}")

# Check overlap of (item_id, condition, prompt_hash, raw_response_text)
exact_match = 0
for r in raw_lines:
    for p in pilot_lines:
        if r['item_id'] == p['item_id'] and r['condition'] == p['condition_id'] and r['raw_response_text'] == p['raw_response']:
            exact_match += 1
            print(f"  EXACT MATCH FOUND with pilot: {r['request_id']} | {r['item_id']} | {r['condition']}")
print(f"Total exact matches between raw/llm.jsonl and pilot: {exact_match}")

