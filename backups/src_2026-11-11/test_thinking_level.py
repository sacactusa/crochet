from google.genai import types

print("ThinkingLevel values:")
for v in types.ThinkingLevel:
    print(f" - {v.name} = {v.value}")

