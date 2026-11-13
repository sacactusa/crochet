from google.genai import types

print("Inspect types related to thinking:")
for attr in dir(types):
    if any(k in attr.lower() for k in ['think', 'budget', 'reason', 'generatecontentconfig']):
        print(f" - {attr}")

try:
    print("\nFields of GenerateContentConfig:")
    cfg = types.GenerateContentConfig()
    for f in dir(cfg):
        if not f.startswith('_'):
            print(f"   {f}: {getattr(cfg, f, None)}")
except Exception as e:
    print("Error:", e)

try:
    print("\nFields of ThinkingConfig:")
    tc = types.ThinkingConfig()
    for f in dir(tc):
        if not f.startswith('_'):
            print(f"   {f}: {getattr(tc, f, None)}")
except Exception as e:
    print("Error ThinkingConfig:", e)

