import os
import sys
import json
import time
from datetime import datetime
from google import genai
from google.genai import types

# 1. Check GEMINI_API_KEY_38 presence and length
key_38 = os.environ.get("GEMINI_API_KEY_38")
if not key_38:
    print("FATAL: GEMINI_API_KEY_38 is not set in environment!", flush=True)
    sys.exit(1)

print(f"1. GEMINI_API_KEY_38 status: PRESENCE = True, LENGTH = {len(key_38)} characters.", flush=True)

# 2. Check client.models.list() for gemini-3.8-flash
print("2. Querying client.models.list() using key_38...", flush=True)
client = genai.Client(
    api_key=key_38,
    http_options=types.HttpOptions(timeout=120000)  # 120 detik
)

try:
    models = list(client.models.list())
    model_names = [m.name for m in models]
    has_38_flash = any("gemini-3.8-flash" in name for name in model_names)
    print(f"   Total models listed: {len(models)}")
    print(f"   gemini-3.8-flash listed: {has_38_flash}", flush=True)
except Exception as e:
    print(f"   Error listing models: {e}", flush=True)
    has_38_flash = False

# 3. Load prompt from prompts/prompts.json
with open("prompts/prompts.json", "r", encoding="utf-8") as f:
    prompts_data = json.load(f)

test_item_key = "early_0"
test_prompt_entry = prompts_data[test_item_key]
test_prompt_text = test_prompt_entry["prompt"]

SYSTEM_PROMPT = """You are a crochet compiler. Translate the next instruction NL into one line of CrochetPARADE DSL.
Use consistent naming and syntax.

Important rules for translations:
1. Make sure your output ONLY contains the DSL code, nothing else.
2. Use the previous examples to understand the pattern of translation.
3. Be consistent in naming conventions with the examples.
4. Your output should be exactly one line of DSL code."""

# Check output log path
log_path = "logs/model_access_38.json"
os.makedirs("logs", exist_ok=True)

trials = []
if os.path.exists(log_path):
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            if isinstance(existing, list):
                trials = existing
            elif isinstance(existing, dict) and "trials" in existing:
                trials = existing["trials"]
    except Exception:
        trials = []

def save_log(summary_classification=None):
    payload = {
        "key_identifier": "key_38",
        "key_length": len(key_38),
        "tested_at": datetime.now().isoformat(),
        "model": "gemini-3.8-flash",
        "classification": summary_classification,
        "trials": trials
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

print("\n3. Starting real calls to gemini-3.8-flash (timeout=120s, max_output_tokens=32768)...", flush=True)

conditions = ["low", "high"]
results_by_level = {}

for level in conditions:
    print(f"\n=======================================================", flush=True)
    print(f"Testing thinking_level='{level}'", flush=True)
    print(f"=======================================================", flush=True)
    
    max_retries = 6
    attempt = 0
    level_success = False

    while attempt < max_retries and not level_success:
        attempt += 1
        timestamp = datetime.now().isoformat()
        print(f"\n[Level: {level}] Attempt {attempt}/{max_retries} at {timestamp}...", flush=True)
        
        cfg = types.GenerateContentConfig(
            max_output_tokens=32768,
            thinking_config=types.ThinkingConfig(thinking_level=level)
        )
        
        # Verify temperature, top_p, top_k are None
        assert cfg.temperature is None, "temperature must not be sent"
        assert cfg.top_p is None, "top_p must not be sent"
        assert cfg.top_k is None, "top_k must not be sent"
        
        t0 = time.time()
        trial_record = {
            "timestamp": timestamp,
            "attempt": attempt,
            "model": "gemini-3.8-flash",
            "thinking_level": level,
            "max_output_tokens": 32768,
            "params_sent": {
                "thinking_level": level,
                "max_output_tokens": 32768,
                "temperature": None,
                "top_p": None,
                "top_k": None
            }
        }
        
        try:
            res = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[SYSTEM_PROMPT, test_prompt_text],
                config=cfg
            )
            elapsed = time.time() - t0
            usage = res.usage_metadata
            finish_reason = None
            if res.candidates and len(res.candidates) > 0:
                finish_reason = str(res.candidates[0].finish_reason)
            
            raw_text = res.text if res.text else ""
            thoughts_tokens = getattr(usage, "thoughts_token_count", None) if usage else None
            prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
            candidates_tokens = getattr(usage, "candidates_token_count", None) if usage else None
            
            trial_record.update({
                "status": "SUCCESS",
                "http_status": 200,
                "elapsed_seconds": round(elapsed, 2),
                "thoughts_token_count": thoughts_tokens,
                "prompt_token_count": prompt_tokens,
                "candidates_token_count": candidates_tokens,
                "finish_reason": finish_reason,
                "raw_response": raw_text,
                "error": None
            })
            trials.append(trial_record)
            save_log()
            
            print(f"SUCCESS in {elapsed:.2f}s!", flush=True)
            print(f" - thoughts_token_count: {thoughts_tokens}", flush=True)
            print(f" - prompt_token_count: {prompt_tokens}", flush=True)
            print(f" - candidates_token_count: {candidates_tokens}", flush=True)
            print(f" - finish_reason: {finish_reason}", flush=True)
            print(f" - raw_response: {raw_text.strip()}", flush=True)
            
            level_success = True
            results_by_level[level] = trial_record
            break
            
        except Exception as e:
            elapsed = time.time() - t0
            err_str = str(e)
            print(f"FAILED attempt {attempt} in {elapsed:.2f}s:", flush=True)
            print(f"Error: {err_str}", flush=True)
            
            # Determine error category
            http_status = None
            if "404" in err_str:
                http_status = 404
            elif "403" in err_str:
                http_status = 403
            elif "400" in err_str:
                http_status = 400
            elif "503" in err_str:
                http_status = 503
            elif "timeout" in err_str.lower() or "timed out" in err_str.lower():
                http_status = "TIMEOUT"
            else:
                http_status = "ERROR"
                
            trial_record.update({
                "status": "FAILED",
                "http_status": http_status,
                "elapsed_seconds": round(elapsed, 2),
                "error_raw": err_str
            })
            trials.append(trial_record)
            save_log()
            
            # Check if permanent error
            if http_status in [404, 403]:
                print(f"Permanent access error ({http_status}). Stopping retries for level={level}.", flush=True)
                results_by_level[level] = trial_record
                break
            elif http_status == 400:
                print(f"Invalid argument error (400). Stopping retries for level={level}.", flush=True)
                results_by_level[level] = trial_record
                break
            elif http_status in [503, "TIMEOUT"] or "503" in err_str or "timed out" in err_str.lower():
                if attempt < max_retries:
                    wait_seconds = 300  # 5 menit
                    print(f"Transient error ({http_status}). Waiting 5 minutes (300s) before retry {attempt+1}...", flush=True)
                    time.sleep(wait_seconds)
                else:
                    print(f"Max retries ({max_retries}) reached for level={level}.", flush=True)
                    results_by_level[level] = trial_record
            else:
                # Other error
                if attempt < max_retries:
                    print(f"Encountered error. Waiting 5 minutes before retry...", flush=True)
                    time.sleep(300)
                else:
                    results_by_level[level] = trial_record

# Final classification
low_res = results_by_level.get("low", {})
high_res = results_by_level.get("high", {})

low_ok = low_res.get("status") == "SUCCESS"
high_ok = high_res.get("status") == "SUCCESS"

low_t = low_res.get("thoughts_token_count")
high_t = high_res.get("thoughts_token_count")

low_finish = low_res.get("finish_reason")
high_finish = high_res.get("finish_reason")

classification = "UNKNOWN"

if low_ok and high_ok:
    if (low_t and low_t > 0) and (high_t and high_t > 0) and ("STOP" in str(low_finish)) and ("STOP" in str(high_finish)):
        classification = "LAYAK"
    else:
        classification = "SUKSES_TETAPI_ANOMALI"
elif any(r.get("http_status") in [404, 403] for r in [low_res, high_res]):
    classification = "AKSES DITOLAK"
elif any(r.get("http_status") == 400 for r in [low_res, high_res]):
    classification = "PARAMETER BERBEDA"
elif any(r.get("http_status") in [503, "TIMEOUT"] for r in [low_res, high_res]):
    classification = "SERVER SIBUK"

save_log(classification)
print(f"\n=======================================================", flush=True)
print(f"FINAL CLASSIFICATION: {classification}", flush=True)
print(f"=======================================================", flush=True)

