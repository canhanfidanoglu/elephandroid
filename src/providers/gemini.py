"""Google Gemini LLM & Embedding provider (cloud API)."""

import json
import logging
import re
from collections.abc import AsyncGenerator

from src.config import settings

from .base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)

# Embedding dimensions for known models
_EMBED_DIMENSIONS = {
    "text-embedding-004": 768,
    "embedding-001": 768,
}


def _get_client():
    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "google-genai package is required for Gemini provider. "
            "Install with: pip install 'elephandroid[gemini]'"
        )
    return genai.Client(api_key=settings.gemini_api_key)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from Gemini response: {text[:500]}")


class GeminiLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return settings.gemini_model

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        client = _get_client()
        from google.genai import types

        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        return _parse_json_response(response.text)

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        client = _get_client()
        from google.genai import types

        system = ""
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])],
                ))

        config = types.GenerateContentConfig(
            temperature=0.3,
        )
        if system:
            config.system_instruction = system

        async for chunk in client.aio.models.generate_content_stream(
            model=settings.gemini_model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    async def health_check(self) -> bool:
        if not settings.gemini_api_key:
            return False
        try:
            client = _get_client()
            await client.aio.models.get(model=settings.gemini_model)
            return True
        except Exception:
            return False


class GeminiEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return _EMBED_DIMENSIONS.get(settings.gemini_embed_model, 768)

    async def embed_text(self, text: str) -> list[float]:
        client = _get_client()
        response = await client.aio.models.embed_content(
            model=settings.gemini_embed_model,
            contents=text,
        )
        return list(response.embeddings[0].values)
