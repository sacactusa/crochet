import time
from google import genai
from google.genai import types

client = genai.Client()
print("Starting call to gemini-3.8-flash...", flush=True)
t0 = time.time()
try:
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        max_output_tokens=100
    )
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Say hi in one word",
        config=cfg
    )
    dt = time.time() - t0
    print(f"Done in {dt:.2f}s!", flush=True)
    print("Response:", res.text, flush=True)
    print("Thoughts token count:", getattr(res.usage_metadata, "thoughts_token_count", None), flush=True)
    print("Candidates token count:", getattr(res.usage_metadata, "candidates_token_count", None), flush=True)
    print("Finish reason:", res.candidates[0].finish_reason, flush=True)
except Exception as e:
    print(f"Error after {time.time()-t0:.2f}s: {type(e)} {e}", flush=True)

