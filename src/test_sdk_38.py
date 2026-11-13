import time
from google import genai
from google.genai import types

client = genai.Client()
print("Calling client.models.generate_content for gemini-3.8-flash...", flush=True)
t0 = time.time()
try:
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Say hello in one word."
    )
    print(f"Success in {time.time()-t0:.2f}s!")
    print("Text:", res.text)
    print("Metadata:", res.usage_metadata)
except Exception as e:
    print(f"Failed in {time.time()-t0:.2f}s: {type(e)} {e}")

