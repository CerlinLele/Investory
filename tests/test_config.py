from investory.config import load_config


def test_load_config_uses_openai_as_default_provider(monkeypatch):
    monkeypatch.delenv("INVESTORY_LLM_PROVIDER", raising=False)

    config = load_config()

    assert config.llm_provider == "openai"
    assert config.default_model == "gpt-5.4-mini"


def test_load_config_reads_provider_from_environment(monkeypatch):
    monkeypatch.setenv("INVESTORY_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("INVESTORY_DEFAULT_MODEL", "claude-sonnet-4-20250514")

    config = load_config()

    assert config.llm_provider == "anthropic"
    assert config.default_model == "claude-sonnet-4-20250514"
