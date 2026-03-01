import logging

from src.config import settings

from .base import LLMProvider

logger = logging.getLogger(__name__)

_llm_instance: LLMProvider | None = None


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
