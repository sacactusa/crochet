from google import genai
from google.genai import types

client = genai.Client()

prompt = "Translate NL: ch 5 into CrochetPARADE DSL."
system_prompt = """You are a crochet compiler. Translate the next instruction NL into one line of CrochetPARADE DSL.
Use consistent naming and syntax.

Important rules for translations:
1. Make sure your output ONLY contains the DSL code, nothing else.
2. Use the previous examples to understand the pattern of translation.
3. Be consistent in naming conventions with the examples.
4. Your output should be exactly one line of DSL code."""

print("--- Test 1: gemini-2.5-flash-lite thinking_budget=0 ---")
try:
    cfg = types.GenerateContentConfig(
        max_output_tokens=32768,
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    res = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[system_prompt, prompt],
        config=cfg
    )
    usage = res.usage_metadata
    print("Success! text:", res.text.strip())
    print("thoughts_token_count:", getattr(usage, "thoughts_token_count", None))
    print("candidates_token_count:", getattr(usage, "candidates_token_count", None))
    print("finish_reason:", res.candidates[0].finish_reason)
except Exception as e:
    print("Error:", e)

print("\n--- Test 2: gemini-2.5-flash-lite thinking_budget=-1 ---")
try:
    cfg = types.GenerateContentConfig(
        max_output_tokens=32768,
        thinking_config=types.ThinkingConfig(thinking_budget=-1)
    )
    res = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[system_prompt, prompt],
        config=cfg
    )
    usage = res.usage_metadata
    print("Success! text:", res.text.strip())
    print("thoughts_token_count:", getattr(usage, "thoughts_token_count", None))
    print("candidates_token_count:", getattr(usage, "candidates_token_count", None))
    print("finish_reason:", res.candidates[0].finish_reason)
except Exception as e:
    print("Error:", e)

print("\n--- Test 3: gemini-3.8-flash thinking_level='low' ---")
try:
    cfg = types.GenerateContentConfig(
        max_output_tokens=32768,
        thinking_config=types.ThinkingConfig(thinking_level="LOW")
    )
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[system_prompt, prompt],
        config=cfg
    )
    usage = res.usage_metadata
    print("Success! text:", res.text.strip())
    print("thoughts_token_count:", getattr(usage, "thoughts_token_count", None))
    print("candidates_token_count:", getattr(usage, "candidates_token_count", None))
    print("finish_reason:", res.candidates[0].finish_reason)
except Exception as e:
    print("Error:", e)

print("\n--- Test 4: gemini-3.8-flash thinking_budget=0 (can it be disabled?) ---")
try:
    cfg = types.GenerateContentConfig(
        max_output_tokens=32768,
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[system_prompt, prompt],
        config=cfg
    )
    usage = res.usage_metadata
    print("Result for 3.8 flash with thinking_budget=0:")
    print("thoughts_token_count:", getattr(usage, "thoughts_token_count", None))
    print("finish_reason:", res.candidates[0].finish_reason)
except Exception as e:
    print("Error when setting thinking_budget=0 on 3.8-flash:", e)

