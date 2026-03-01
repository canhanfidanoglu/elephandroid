import json
import logging
import re
from collections.abc import AsyncGenerator

from src.config import settings

from .base import LLMProvider

logger = logging.getLogger(__name__)


def _get_client():
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package is required for Claude provider. "
            "Install with: pip install 'elephandroid[claude]'"
        )
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Claude response, handling markdown fences."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try markdown fenced block
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from Claude response: {text[:500]}")


class ClaudeLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return settings.anthropic_model

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        client = _get_client()
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = response.content[0].text
        return _parse_json_response(raw_text)

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        client = _get_client()

        # Separate system prompt from messages
        system = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=4096,
            temperature=0.3,
            system=system,
            messages=chat_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        if not settings.anthropic_api_key:
            return False
        try:
            client = _get_client()
            await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False
