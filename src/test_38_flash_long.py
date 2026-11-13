import os
import requests
import json
import time

api_key = os.environ.get("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

payload = {
    "contents": [{"parts": [{"text": "hi"}]}]
}

print("Testing gemini-3.8-flash with timeout=90s...", flush=True)
t0 = time.time()
try:
    r = requests.post(url, json=payload, timeout=90)
    dt = time.time() - t0
    print(f"Status: {r.status_code} in {dt:.2f}s", flush=True)
    res_data = r.json()
    print("Response JSON keys:", res_data.keys(), flush=True)
    if "candidates" in res_data:
        c = res_data["candidates"][0]
        print("Candidate finishReason:", c.get("finishReason"), flush=True)
        parts = c.get("content", {}).get("parts", [])
        for p in parts:
            if "text" in p:
                print("Text:", p["text"], flush=True)
            if "thought" in p or "thoughtSignature" in p:
                print("Thought part found! Keys:", p.keys(), flush=True)
    if "usageMetadata" in res_data:
        print("usageMetadata:", res_data["usageMetadata"], flush=True)
except Exception as e:
    print(f"Error after {time.time()-t0:.2f}s: {e}", flush=True)

