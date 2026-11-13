import os
from google import genai

key_25 = os.environ.get("GEMINI_API_KEY_25")
print(f"Connecting with key_25 (length={len(key_25)})...", flush=True)

client = genai.Client(api_key=key_25)

try:
    models = list(client.models.list())
    names = [m.name for m in models]
    print(f"Total models accessible with key_25: {len(models)}")
    has_25_lite = any("gemini-2.5-flash-lite" in n for n in names)
    has_25_flash = any("gemini-2.5-flash" in n and "lite" not in n for n in names)
    print(f" - gemini-2.5-flash-lite listed: {has_25_lite}")
    print(f" - gemini-2.5-flash listed: {has_25_flash}")
    for n in names:
        if "2.5" in n:
            print("   *", n)
except Exception as e:
    print(f"Error listing models with key_25: {e}")

