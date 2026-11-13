import os
import requests
import json
import time

api_key = os.environ.get("GEMINI_API_KEY")
print(f"Testing direct REST call with api_key: {api_key[:6]}...", flush=True)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

payload = {
    "contents": [
        {
            "parts": [
                {"text": "Say hi in one word"}
            ]
        }
    ],
    "generationConfig": {
        "maxOutputTokens": 100,
        "thinkingConfig": {
            "thinkingLevel": "LOW"
        }
    }
}

t0 = time.time()
try:
    print("Sending POST request to REST endpoint...", flush=True)
    resp = requests.post(url, json=payload, timeout=30)
    print(f"Status code: {resp.status_code} in {time.time()-t0:.2f}s", flush=True)
    print("Response body:", resp.text[:500], flush=True)
except Exception as e:
    print(f"Request error after {time.time()-t0:.2f}s: {e}", flush=True)

