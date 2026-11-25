import os
from typing import List, Optional

from google import genai

from app.core.config import settings


def generate_embeddings(
    texts: List[str],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> List[List[float]]:
    if not texts:
        return []

    resolved_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not resolved_key:
        raise RuntimeError("Gemini API key is not configured for embeddings.")

    resolved_model = (
        model or os.getenv("GEMINI_EMBEDDING_MODEL", settings.gemini_embedding_model)
    ).strip()

    client = genai.Client(api_key=resolved_key)
    vectors: List[List[float]] = []

    # Process in modest batches to respect API payload limits
    batch_size = 20
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.models.embed_content(
            model=resolved_model,
            contents=batch,
        )
        embeddings = getattr(response, "embeddings", None) or []
        for item in embeddings:
            values = getattr(item, "values", None)
            if not values:
                raise ValueError("Gemini returned an empty embedding vector.")
            vectors.append(list(values))

    if len(vectors) != len(texts):
        raise ValueError("Embedding count mismatch returned by Gemini.")

    return vectors
