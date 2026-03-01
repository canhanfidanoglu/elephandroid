import logging

from src.config import settings

from .base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)

_llm_instance: LLMProvider | None = None
_embed_instance: EmbeddingProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Return a lazy singleton LLM provider based on settings.llm_provider."""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    provider = settings.llm_provider.lower()

    if provider == "ollama":
        from .ollama import OllamaLLMProvider
        _llm_instance = OllamaLLMProvider()

    elif provider == "claude":
        from .claude import ClaudeLLMProvider
        _llm_instance = ClaudeLLMProvider()

    elif provider == "openai":
        from .openai_provider import OpenAILLMProvider
        _llm_instance = OpenAILLMProvider()

    elif provider == "gemini":
        from .gemini import GeminiLLMProvider
        _llm_instance = GeminiLLMProvider()

    elif provider == "gemma":
        from .ollama import OllamaLLMProvider
        _llm_instance = OllamaLLMProvider(override_model="gemma3", override_name="gemma")

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            "Supported: 'ollama', 'claude', 'openai', 'gemini', 'gemma'"
        )

    logger.info("LLM provider: %s (%s)", _llm_instance.provider_name, _llm_instance.model_name)
    return _llm_instance


def get_embedding_provider() -> EmbeddingProvider:
    """Return a lazy singleton embedding provider based on settings.embedding_provider."""
    global _embed_instance
    if _embed_instance is not None:
        return _embed_instance

    provider = settings.embedding_provider.lower()

    if provider == "ollama":
        from .ollama import OllamaEmbeddingProvider
        _embed_instance = OllamaEmbeddingProvider()

    elif provider == "openai":
        from .openai_provider import OpenAIEmbeddingProvider
        _embed_instance = OpenAIEmbeddingProvider()

    elif provider == "gemini":
        from .gemini import GeminiEmbeddingProvider
        _embed_instance = GeminiEmbeddingProvider()

    else:
        raise ValueError(
            f"Unknown embedding provider: '{provider}'. "
            "Supported: 'ollama', 'openai', 'gemini'"
        )

    logger.info("Embedding provider: %s (dim=%d)", provider, _embed_instance.dimension)
    return _embed_instance
