import os
import requests
import json
import time

api_key = os.environ.get("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"

payload = {
    "contents": [{"parts": [{"text": "hi"}]}]
}

try:
    r = requests.post(url, json=payload, timeout=60)
    print("Status:", r.status_code)
    print("Text:", r.text)
except Exception as e:
    print("Exception:", e)

