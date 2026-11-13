import os
import sys
import json
import time
from datetime import datetime
from google import genai
from google.genai import types

key_25 = os.environ.get("GEMINI_API_KEY_25")
if not key_25:
    print("FATAL: GEMINI_API_KEY_25 is not set!", flush=True)
    sys.exit(1)

client = genai.Client(
    api_key=key_25,
    http_options=types.HttpOptions(timeout=180000)  # 180 detik
)

SYSTEM_PROMPT = """You are a crochet compiler. Translate the next instruction NL into one line of CrochetPARADE DSL.
Use consistent naming and syntax.

Important rules for translations:
1. Make sure your output ONLY contains the DSL code, nothing else.
2. Use the previous examples to understand the pattern of translation.
3. Be consistent in naming conventions with the examples.
4. Your output should be exactly one line of DSL code."""

with open("prompts/prompts.json", "r", encoding="utf-8") as f:
    prompts_data = json.load(f)

# Take 5 pilot items
pilot_keys = ["early_0", "early_1", "early_2", "early_3", "early_4"]

conditions = [
    {
        "condition_id": "L25L-OFF",
        "model_id": "gemini-2.5-flash-lite",
        "thinking_budget": 0
    },
    {
        "condition_id": "L25L-ON",
        "model_id": "gemini-2.5-flash-lite",
        "thinking_budget": -1
    },
    {
        "condition_id": "L25F-OFF",
        "model_id": "gemini-2.5-flash",
        "thinking_budget": 0
    },
    {
        "condition_id": "L25F-ON",
        "model_id": "gemini-2.5-flash",
        "thinking_budget": -1
    }
]

os.makedirs("logs", exist_ok=True)
pilot_log_path = "logs/pilot_25.jsonl"

records = []
print(f"Starting Pilot for Gemini 2.5 (key_25) across {len(pilot_keys)} items and {len(conditions)} conditions...\n", flush=True)

for cond in conditions:
    cid = cond["condition_id"]
    mid = cond["model_id"]
    budget = cond["thinking_budget"]
    print(f"===========================================================", flush=True)
    print(f"Condition: {cid} | Model: {mid} | thinking_budget={budget}", flush=True)
    print(f"===========================================================", flush=True)
    
    cfg = types.GenerateContentConfig(
        max_output_tokens=32768,
        thinking_config=types.ThinkingConfig(thinking_budget=budget)
    )
    
    # Ensure no temperature, top_p, top_k are sent
    assert cfg.temperature is None, "temperature must not be sent"
    assert cfg.top_p is None, "top_p must not be sent"
    assert cfg.top_k is None, "top_k must not be sent"
    
    for ikey in pilot_keys:
        p_entry = prompts_data[ikey]
        prompt_text = p_entry["prompt"]
        prompt_hash = p_entry["prompt_hash"]
        
        t0 = time.time()
        timestamp = datetime.now().isoformat()
        try:
            res = client.models.generate_content(
                model=mid,
                contents=[SYSTEM_PROMPT, prompt_text],
                config=cfg
            )
            elapsed = time.time() - t0
            usage = res.usage_metadata
            finish_reason = str(res.candidates[0].finish_reason) if res.candidates else None
            raw_text = res.text.strip() if res.text else ""
            
            thoughts_tokens = getattr(usage, "thoughts_token_count", None) if usage else None
            prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
            candidates_tokens = getattr(usage, "candidates_token_count", None) if usage else None
            
            # Check truncation
            is_truncated = (finish_reason == "FinishReason.MAX_TOKENS" or finish_reason == "MAX_TOKENS")
            
            rec = {
                "pilot": True,
                "timestamp": timestamp,
                "item_id": ikey,
                "id": p_entry["id"],
                "condition_id": cid,
                "model_id": mid,
                "params_sent": {
                    "thinking_budget": budget,
                    "max_output_tokens": 32768,
                    "temperature": None,
                    "top_p": None,
                    "top_k": None
                },
                "prompt_hash": prompt_hash,
                "raw_response": raw_text,
                "finish_reason": finish_reason,
                "tokens_in": prompt_tokens,
                "tokens_out": candidates_tokens,
                "tokens_thinking": thoughts_tokens if thoughts_tokens is not None else 0,
                "elapsed_seconds": round(elapsed, 2),
                "is_truncated": is_truncated,
                "error": None
            }
            records.append(rec)
            print(f"[{cid}] Item {ikey}: SUCCESS in {elapsed:.2f}s | thinking={rec['tokens_thinking']} | out={candidates_tokens} | finish={finish_reason} | resp={raw_text[:40]}", flush=True)
            
        except Exception as e:
            elapsed = time.time() - t0
            rec = {
                "pilot": True,
                "timestamp": timestamp,
                "item_id": ikey,
                "id": p_entry["id"],
                "condition_id": cid,
                "model_id": mid,
                "params_sent": {
                    "thinking_budget": budget,
                    "max_output_tokens": 32768
                },
                "prompt_hash": prompt_hash,
                "raw_response": "",
                "finish_reason": "ERROR",
                "tokens_in": None,
                "tokens_out": None,
                "tokens_thinking": None,
                "elapsed_seconds": round(elapsed, 2),
                "is_truncated": False,
                "error": str(e)
            }
            records.append(rec)
            print(f"[{cid}] Item {ikey}: FAILED in {elapsed:.2f}s: {e}", flush=True)
            
        time.sleep(1.0)  # Gentle spacing between requests

# Write to logs/pilot_25.jsonl
with open(pilot_log_path, "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r) + "\n")

print(f"\nAll {len(records)} pilot records saved to {pilot_log_path}")

# Generate model access summary for logs/model_access.json
summary_by_cond = {}
for cond in conditions:
    cid = cond["condition_id"]
    cond_records = [r for r in records if r["condition_id"] == cid]
    success_records = [r for r in cond_records if r["error"] is None]
    
    thinking_counts = [r["tokens_thinking"] for r in success_records]
    elapsed_times = [r["elapsed_seconds"] for r in success_records]
    truncations = [r["is_truncated"] for r in success_records]
    finish_reasons = list(set(r["finish_reason"] for r in success_records))
    
    summary_by_cond[cid] = {
        "model_id": cond["model_id"],
        "thinking_budget": cond["thinking_budget"],
        "total_requests": len(cond_records),
        "successful_requests": len(success_records),
        "failed_requests": len(cond_records) - len(success_records),
        "finish_reasons": finish_reasons,
        "any_truncated": any(truncations),
        "thinking_tokens": {
            "all": thinking_counts,
            "min": min(thinking_counts) if thinking_counts else None,
            "max": max(thinking_counts) if thinking_counts else None,
            "avg": round(sum(thinking_counts)/len(thinking_counts), 1) if thinking_counts else None,
            "check_rule": "OFF==0" if cond["thinking_budget"] == 0 else "ON>0",
            "check_passed": all(t == 0 for t in thinking_counts) if cond["thinking_budget"] == 0 else all(t > 0 for t in thinking_counts)
        },
        "response_time_seconds": {
            "min": min(elapsed_times) if elapsed_times else None,
            "max": max(elapsed_times) if elapsed_times else None,
            "avg": round(sum(elapsed_times)/len(elapsed_times), 2) if elapsed_times else None
        }
    }

model_access_doc = {
    "gemini_25_key_identifier": "key_25",
    "gemini_25_key_length": len(key_25),
    "gemini_38_key_identifier": "key_38",
    "gemini_38_key_length": 53,
    "pilot_tested_at": datetime.now().isoformat(),
    "rate_limits": {
        "gemini-2.5-flash-lite": {
            "tier": "Free Tier",
            "rpm": 15,
            "rpd": 1500,
            "tpm": 1000000,
            "source": "Google AI Studio Documentation (ai.google.dev/pricing)"
        },
        "gemini-2.5-flash": {
            "tier": "Free Tier",
            "rpm": 15,
            "rpd": 1500,
            "tpm": 1000000,
            "source": "Google AI Studio Documentation (ai.google.dev/pricing)"
        },
        "gemini-3.8-flash": {
            "tier": "Free Tier",
            "rpm": 15,
            "rpd": 20,
            "tpm": 1000000,
            "source": "Empirically Verified from API Error Quota Value (GenerateRequestsPerDayPerProjectPerModel-FreeTier: 20)"
        }
    },
    "pilot_manipulation_check_results": summary_by_cond
}

with open("logs/model_access.json", "w", encoding="utf-8") as f:
    json.dump(model_access_doc, f, indent=2)

print("\nSaved logs/model_access.json:")
print(json.dumps(model_access_doc, indent=2))

