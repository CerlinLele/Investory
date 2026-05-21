from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from investory.agent_core.runtime.model_factory import create_chat_model
from investory.config import LLM_PROVIDERS, AppConfig


class FakeChatModel:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _install_fake_provider(monkeypatch, module_name: str, class_name: str) -> None:
    module = ModuleType(module_name)
    setattr(module, class_name, FakeChatModel)
    monkeypatch.setitem(sys.modules, module_name, module)


def test_create_chat_model_builds_openai_model_from_environment(monkeypatch):
    _install_fake_provider(monkeypatch, "langchain_openai", "ChatOpenAI")
    monkeypatch.setenv("INVESTORY_LLM_PROVIDER", "openai")
    monkeypatch.setenv("INVESTORY_DEFAULT_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("INVESTORY_LLM_TEMPERATURE", "0.1")
    monkeypatch.setenv("INVESTORY_LLM_MAX_RETRIES", "4")

    model = create_chat_model()

    assert model.kwargs == {
        "model": "gpt-test",
        "api_key": "test-openai-key",
        "base_url": "https://example.test/v1",
        "temperature": 0.1,
        "max_retries": 0,
    }


def test_create_chat_model_builds_anthropic_model(monkeypatch):
    _install_fake_provider(monkeypatch, "langchain_anthropic", "ChatAnthropic")
    config = AppConfig(
        llm_provider="anthropic",
        default_model="claude-test",
        llm_base_url="https://example.test/anthropic",
        llm_api_key="test-anthropic-key",
        llm_temperature=0.2,
        llm_max_retries=3,
        llm_provider_config=LLM_PROVIDERS["anthropic"],
    )

    model = create_chat_model(config)

    assert model.kwargs == {
        "model": "claude-test",
        "api_key": "test-anthropic-key",
        "base_url": "https://example.test/anthropic",
        "temperature": 0.2,
        "max_retries": 0,
    }


def test_create_chat_model_builds_google_genai_model(monkeypatch):
    _install_fake_provider(
        monkeypatch,
        "langchain_google_genai",
        "ChatGoogleGenerativeAI",
    )
    config = AppConfig(
        llm_provider="google_genai",
        default_model="gemini-test",
        llm_base_url="https://example.test/google",
        llm_api_key="test-google-key",
        llm_temperature=0,
        llm_max_retries=2,
        llm_provider_config=LLM_PROVIDERS["google_genai"],
    )

    model = create_chat_model(config)

    assert model.kwargs == {
        "model": "gemini-test",
        "google_api_key": "test-google-key",
        "temperature": 0,
        "max_retries": 0,
    }
