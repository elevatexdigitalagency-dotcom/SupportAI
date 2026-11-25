from typing import Optional

from google import genai

from app.core.config import settings


def generate_gemini_reply(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    resolved_key = (api_key or settings.gemini_api_key).strip()
    if not resolved_key:
        raise RuntimeError("Gemini API key is not configured.")

    resolved_model = (model or settings.gemini_model).strip()
    client = genai.Client(api_key=resolved_key)
    response = client.models.generate_content(
        model=resolved_model,
        contents=prompt,
    )
    answer = response.text
    if not answer:
        raise ValueError("Gemini returned an empty response.")
    return answer
