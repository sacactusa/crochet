from google import genai
from google.genai import types

client = genai.Client()

models_to_test = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.8-flash"
]

for m in models_to_test:
    print(f"\n================ Testing model: {m} ================", flush=True)
    try:
        res = client.models.generate_content(
            model=m,
            contents="Say hi in one word"
        )
        print(f"SUCCESS on {m}!")
        print(f"Response text: {res.text.strip()}")
        print(f"Usage metadata: {res.usage_metadata}")
    except Exception as e:
        print(f"FAILED on {m}:")
        print(f"Error type: {type(e)}")
        print(f"Error detail: {e}")

