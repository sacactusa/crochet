import os
import requests
import time

api_key = os.environ.get("GEMINI_API_KEY")

test_models = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite"
]

results = []
for m in test_models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "hi"}]}]}
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=10)
        dt = time.time() - t0
        err_msg = ""
        if r.status_code != 200:
            try:
                err_msg = r.json().get("error", {}).get("message", r.text[:100])
            except Exception:
                err_msg = r.text[:100]
        results.append((m, r.status_code, f"{dt:.2f}s", err_msg))
    except Exception as e:
        results.append((m, "TIMEOUT/ERR", f"{time.time()-t0:.2f}s", str(e)))

print(f"{'Model':<30} | {'Status':<10} | {'Time':<8} | {'Error / Note'}")
print("-" * 80)
for m, st, dt, note in results:
    print(f"{m:<30} | {str(st):<10} | {dt:<8} | {note[:60]}")

