import pytest

from investory.config import LLM_PROVIDERS, get_llm_provider_config, load_config


def test_load_config_uses_openai_as_default_provider(monkeypatch):
    monkeypatch.delenv("INVESTORY_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("INVESTORY_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    config = load_config(env_file=None)

    assert config.llm_provider == "openai"
    assert config.default_model == "gpt-5.4-mini"
    assert config.llm_base_url == "https://api.openai.com/v1"
    assert config.llm_provider_config == LLM_PROVIDERS["openai"]


def test_load_config_reads_provider_settings_from_environment(monkeypatch):
    monkeypatch.setenv("INVESTORY_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("INVESTORY_DEFAULT_MODEL", "claude-sonnet-4-20250514")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.test/anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("INVESTORY_LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("INVESTORY_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("INVESTORY_LOG_LEVEL", "debug")

    config = load_config(env_file=None)

    assert config.llm_provider == "anthropic"
    assert config.default_model == "claude-sonnet-4-20250514"
    assert config.llm_base_url == "https://example.test/anthropic"
    assert config.llm_api_key == "test-anthropic-key"
    assert config.llm_temperature == 0.2
    assert config.llm_max_retries == 3
    assert config.log_level == "DEBUG"


def test_load_config_uses_provider_default_model_when_model_is_unset(monkeypatch):
    monkeypatch.setenv("INVESTORY_LLM_PROVIDER", "google_genai")
    monkeypatch.delenv("INVESTORY_DEFAULT_MODEL", raising=False)

    config = load_config(env_file=None)

    assert config.default_model == "gemini-2.5-flash"
    assert config.llm_provider_config.api_key_env == "GOOGLE_API_KEY"


def test_get_llm_provider_config_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider_config("unknown")


def test_load_config_reads_local_env_file_without_overriding_environment(
    monkeypatch,
    tmp_path,
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "INVESTORY_LLM_PROVIDER=openai",
                "OPENAI_BASE_URL=https://api.fe8.cn/v1",
                "OPENAI_API_KEY=key-from-file",
                "INVESTORY_LLM_TEMPERATURE=0.3",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("INVESTORY_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("INVESTORY_DEFAULT_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "key-from-shell")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("INVESTORY_LLM_TEMPERATURE", raising=False)

    config = load_config(env_file=env_file)

    assert config.llm_base_url == "https://api.fe8.cn/v1"
    assert config.llm_api_key == "key-from-shell"
    assert config.llm_temperature == 0.3
