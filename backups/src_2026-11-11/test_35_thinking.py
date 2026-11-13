import os, requests, json, time
from google import genai
from google.genai import types

client = genai.Client()

print("Testing gemini-3.5-flash-lite thinking_budget=0...")
try:
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    r = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say hi",
        config=cfg
    )
    print("Success! text:", r.text.strip())
    print("thoughts_token_count:", getattr(r.usage_metadata, "thoughts_token_count", None))
except Exception as e:
    print("Error:", e)

print("\nTesting gemini-3.5-flash-lite thinking_budget=-1...")
try:
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=-1)
    )
    r = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say hi",
        config=cfg
    )
    print("Success! text:", r.text.strip())
    print("thoughts_token_count:", getattr(r.usage_metadata, "thoughts_token_count", None))
except Exception as e:
    print("Error:", e)

print("\nTesting gemini-3.5-flash thinking_budget=0...")
try:
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    r = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Say hi",
        config=cfg
    )
    print("Success! text:", r.text.strip())
    print("thoughts_token_count:", getattr(r.usage_metadata, "thoughts_token_count", None))
except Exception as e:
    print("Error:", e)

print("\nTesting gemini-3.5-flash thinking_budget=-1...")
try:
    cfg = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=-1)
    )
    r = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Say hi",
        config=cfg
    )
    print("Success! text:", r.text.strip())
    print("thoughts_token_count:", getattr(r.usage_metadata, "thoughts_token_count", None))
except Exception as e:
    print("Error:", e)

