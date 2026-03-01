from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class LLMProvider(ABC):
    @abstractmethod
    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Generate a JSON response from the LLM (temp ~0.1)."""

    @abstractmethod
    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Stream chat completion chunks (temp ~0.3)."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier, e.g. 'ollama', 'claude', 'openai'."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Currently configured model name."""


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Return the embedding vector for the given text."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimension of the embedding vectors."""
