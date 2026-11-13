import sys
from google import genai
from google.genai import types

print("Initializing client...", flush=True)
client = genai.Client()

print("Calling generate_content on gemini-2.5-flash-lite...", flush=True)
try:
    cfg = types.GenerateContentConfig(
        max_output_tokens=100,
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    res = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents="Say hi in one word",
        config=cfg
    )
    print("Response text:", res.text, flush=True)
    print("Usage metadata:", res.usage_metadata, flush=True)
except Exception as e:
    print("Error:", type(e), e, flush=True)

