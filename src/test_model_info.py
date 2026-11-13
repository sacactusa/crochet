from google import genai

client = genai.Client()
for m_id in ['gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-3.8-flash']:
    try:
        m = client.models.get(model=m_id)
        print(f"=== Model: {m_id} ===")
        print(f"  Name: {m.name}")
        print(f"  Display: {getattr(m, 'display_name', '')}")
        print(f"  Input token limit: {getattr(m, 'input_token_limit', '')}")
        print(f"  Output token limit: {getattr(m, 'output_token_limit', '')}")
        print(f"  Supported methods: {getattr(m, 'supported_generation_methods', '')}")
        # Check rate limits if present in attributes
        for attr in dir(m):
            if any(k in attr.lower() for k in ['rate', 'rpm', 'rpd', 'tpm', 'limit', 'quota']):
                print(f"  {attr}: {getattr(m, attr)}")
    except Exception as e:
        print(f"Error getting {m_id}: {e}")

