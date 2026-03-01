"""Multi-LLM provider abstraction.

Public API — use these functions instead of importing specific providers.
"""

from collections.abc import AsyncGenerator

from .factory import get_embedding_provider, get_llm_provider


async def generate_json(system_prompt: str, user_prompt: str) -> dict:
    return await get_llm_provider().generate_json(system_prompt, user_prompt)


async def stream_chat(messages: list[dict]) -> AsyncGenerator[str, None]:
    async for chunk in get_llm_provider().stream_chat(messages):
        yield chunk


async def embed_text(text: str) -> list[float]:
    return await get_embedding_provider().embed_text(text)


async def health_check() -> bool:
    return await get_llm_provider().health_check()
