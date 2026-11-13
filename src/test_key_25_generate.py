import os
import time
from google import genai
from google.genai import types

key_25 = os.environ.get("GEMINI_API_KEY_25")
client = genai.Client(
    api_key=key_25,
    http_options=types.HttpOptions(timeout=180000)
)

tests = [
    ("gemini-2.5-flash-lite", 0, "L25L-OFF"),
    ("gemini-2.5-flash-lite", -1, "L25L-ON"),
    ("gemini-2.5-flash", 0, "L25F-OFF"),
    ("gemini-2.5-flash", -1, "L25F-ON")
]

for model, budget, cond_name in tests:
    print(f"\nTesting {cond_name} ({model}, thinking_budget={budget})...", flush=True)
    t0 = time.time()
    try:
        cfg = types.GenerateContentConfig(
            max_output_tokens=32768,
            thinking_config=types.ThinkingConfig(thinking_budget=budget)
        )
        res = client.models.generate_content(
            model=model,
            contents="Say hi in one word",
            config=cfg
        )
        dt = time.time() - t0
        usage = res.usage_metadata
        finish = res.candidates[0].finish_reason if res.candidates else None
        print(f"SUCCESS in {dt:.2f}s! Text: {res.text.strip()}", flush=True)
        print(f" - thoughts_token_count: {getattr(usage, 'thoughts_token_count', None)}", flush=True)
        print(f" - prompt_token_count: {getattr(usage, 'prompt_token_count', None)}", flush=True)
        print(f" - candidates_token_count: {getattr(usage, 'candidates_token_count', None)}", flush=True)
        print(f" - finish_reason: {finish}", flush=True)
    except Exception as e:
        dt = time.time() - t0
        print(f"FAILED in {dt:.2f}s: {e}", flush=True)

