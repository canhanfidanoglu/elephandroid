"""Tests for provider factory and provider properties."""

from unittest.mock import patch

import pytest

from src.providers.base import EmbeddingProvider, LLMProvider
from src.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider


class TestOllamaLLMProvider:
    def test_default_provider_name(self):
        p = OllamaLLMProvider()
        assert p.provider_name == "ollama"

    def test_default_model_from_settings(self):
        p = OllamaLLMProvider()
        assert p.model_name  # whatever settings says

    def test_override_model(self):
        p = OllamaLLMProvider(override_model="gemma3", override_name="gemma")
        assert p.provider_name == "gemma"
        assert p.model_name == "gemma3"
        assert p._model == "gemma3"

    def test_override_only_model(self):
        p = OllamaLLMProvider(override_model="llama3")
        assert p.provider_name == "ollama"
        assert p.model_name == "llama3"

    def test_implements_interface(self):
        p = OllamaLLMProvider()
        assert isinstance(p, LLMProvider)


class TestOllamaEmbeddingProvider:
    def test_dimension(self):
        p = OllamaEmbeddingProvider()
        assert p.dimension == 768

    def test_implements_interface(self):
        p = OllamaEmbeddingProvider()
        assert isinstance(p, EmbeddingProvider)


class TestProviderFactory:
    def test_ollama_llm(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            # Reset singleton
            import src.providers.factory as fmod
            fmod._llm_instance = None
            provider = fmod.get_llm_provider()
            assert provider.provider_name == "ollama"
            fmod._llm_instance = None  # cleanup

    def test_gemma_llm(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.llm_provider = "gemma"
            import src.providers.factory as fmod
            fmod._llm_instance = None
            provider = fmod.get_llm_provider()
            assert provider.provider_name == "gemma"
            assert provider.model_name == "gemma3"
            fmod._llm_instance = None

    def test_unknown_llm_raises(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.llm_provider = "nonexistent"
            import src.providers.factory as fmod
            fmod._llm_instance = None
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                fmod.get_llm_provider()
            fmod._llm_instance = None

    def test_unknown_embedding_raises(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.embedding_provider = "nonexistent"
            import src.providers.factory as fmod
            fmod._embed_instance = None
            with pytest.raises(ValueError, match="Unknown embedding provider"):
                fmod.get_embedding_provider()
            fmod._embed_instance = None

    def test_singleton_returns_same_instance(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            import src.providers.factory as fmod
            fmod._llm_instance = None
            p1 = fmod.get_llm_provider()
            p2 = fmod.get_llm_provider()
            assert p1 is p2
            fmod._llm_instance = None

    def test_ollama_embedding(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.embedding_provider = "ollama"
            import src.providers.factory as fmod
            fmod._embed_instance = None
            provider = fmod.get_embedding_provider()
            assert provider.dimension == 768
            fmod._embed_instance = None


class TestGeminiProvider:
    def test_provider_properties(self):
        from src.providers.gemini import GeminiLLMProvider, GeminiEmbeddingProvider

        llm = GeminiLLMProvider()
        assert llm.provider_name == "gemini"
        assert isinstance(llm, LLMProvider)

        emb = GeminiEmbeddingProvider()
        assert emb.dimension == 768
        assert isinstance(emb, EmbeddingProvider)

    def test_gemini_factory(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.llm_provider = "gemini"
            import src.providers.factory as fmod
            fmod._llm_instance = None
            provider = fmod.get_llm_provider()
            assert provider.provider_name == "gemini"
            fmod._llm_instance = None

    def test_gemini_embedding_factory(self):
        with patch("src.providers.factory.settings") as mock_settings:
            mock_settings.embedding_provider = "gemini"
            import src.providers.factory as fmod
            fmod._embed_instance = None
            provider = fmod.get_embedding_provider()
            assert provider.dimension == 768
            fmod._embed_instance = None
