import json
import logging
from collections.abc import AsyncGenerator

import httpx

from src.config import settings

from .base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    def __init__(self, override_model: str = "", override_name: str = ""):
        self._override_model = override_model
        self._override_name = override_name

    @property
    def provider_name(self) -> str:
        return self._override_name or "ollama"

    @property
    def model_name(self) -> str:
        return self._override_model or settings.ollama_model

    @property
    def _model(self) -> str:
        return self._override_model or settings.ollama_model

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = {
            "model": self._model,
            "system": system_prompt,
            "prompt": user_prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()

        data = resp.json()
        raw_text = data.get("response", "")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("Ollama returned non-JSON response: %s", raw_text[:500])
            raise ValueError(f"Ollama response is not valid JSON: {exc}") from exc

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": 0.3},
        }
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done", False):
                        break

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.ollama_base_url}/")
                return resp.status_code == 200
        except Exception:
            return False


class OllamaEmbeddingProvider(EmbeddingProvider):
    @property
    def dimension(self) -> int:
        return 768

    async def embed_text(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": text},
            )
            resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]
