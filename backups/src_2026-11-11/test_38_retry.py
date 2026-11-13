import os, requests, json, time

api_key = os.environ.get("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

payload = {
    "contents": [{"parts": [{"text": "Say ok"}]}],
    "generationConfig": {"thinkingConfig": {"thinkingLevel": "LOW"}}
}

t0 = time.time()
try:
    r = requests.post(url, json=payload, timeout=40)
    print("Status:", r.status_code, f"({time.time()-t0:.2f}s)")
    print("Body:", r.text[:300])
except Exception as e:
    print("Err:", e)

