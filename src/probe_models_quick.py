import os
import requests
import json
import time

api_key = os.environ.get("GEMINI_API_KEY")

for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "hi"}]}]}
    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"[{model}] {r.status_code} ({time.time()-t0:.2f}s): {r.text[:200]}")
    except Exception as e:
        print(f"[{model}] Error ({time.time()-t0:.2f}s): {e}")

