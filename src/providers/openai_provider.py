import json
import logging
from collections.abc import AsyncGenerator

from src.config import settings

from .base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)

# Embedding dimensions for known models
_EMBED_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def _get_client():
    try:
        import openai
    except ImportError:
        raise ImportError(
            "openai package is required for OpenAI provider. "
            "Install with: pip install 'elephandroid[openai]'"
        )
    return openai.AsyncOpenAI(api_key=settings.openai_api_key)


class OpenAILLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return settings.openai_model

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_text = response.choices[0].message.content
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("OpenAI returned non-JSON response: %s", raw_text[:500])
            raise ValueError(f"OpenAI response is not valid JSON: {exc}") from exc

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        client = _get_client()
        stream = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def health_check(self) -> bool:
        if not settings.openai_api_key:
            return False
        try:
            client = _get_client()
            await client.models.retrieve(settings.openai_model)
            return True
        except Exception:
            return False


class OpenAIEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return _EMBED_DIMENSIONS.get(settings.openai_embed_model, 1536)

    async def embed_text(self, text: str) -> list[float]:
        client = _get_client()
        response = await client.embeddings.create(
            model=settings.openai_embed_model,
            input=text,
        )
        return response.data[0].embedding
