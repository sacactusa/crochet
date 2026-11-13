import os
from google import genai
from google.genai import types

client = genai.Client()
print("Querying client.models.list()...")
try:
    models = list(client.models.list())
    print(f"Total models returned: {len(models)}")
    relevant = []
    for m in models:
        name = m.name or ""
        display = getattr(m, "display_name", "")
        if any(k in name.lower() for k in ["2.5", "3.8", "flash"]):
            relevant.append((name, display))
            print(f" - {name} ({display})")
    if not relevant:
        print("No matching 2.5/3.8/flash models found in list.")
        for m in models[:10]:
            print(f" - {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")

