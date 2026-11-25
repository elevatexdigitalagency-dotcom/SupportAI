
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")

print("Key loaded:", bool(key))
print("Model:", model)

if not key:
    raise SystemExit("Missing Gemini API key")

try:
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model,
        contents="Say hello to SupportAI in one sentence."
    )
    print("SUCCESS:", response.text)

except Exception as e:
    print("ERROR:", type(e).__name__)
    print(str(e))
