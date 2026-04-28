"""Factory for LangChain chat model instances."""

from __future__ import annotations

from typing import Any

from investory.config import AppConfig, load_config


def _provider_import_error(package: str, provider: str) -> ImportError:
    return ImportError(
        f"LLM provider '{provider}' requires package '{package}'. "
        f"Install it before using INVESTORY_LLM_PROVIDER={provider}."
    )


def _common_model_kwargs(config: AppConfig) -> dict[str, Any]:
    return {
        "temperature": config.llm_temperature,
        "max_retries": config.llm_max_retries,
    }


def create_chat_model(config: AppConfig | None = None) -> Any:
    """Create a LangChain chat model for the configured provider."""

    resolved_config = config or load_config()
    provider = resolved_config.llm_provider
    provider_config = resolved_config.llm_provider_config
    common = _common_model_kwargs(resolved_config)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ModuleNotFoundError as exc:
            raise _provider_import_error(provider_config.package, provider) from exc

        return ChatOpenAI(
            model=resolved_config.default_model,
            api_key=resolved_config.llm_api_key,
            base_url=resolved_config.llm_base_url,
            **common,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ModuleNotFoundError as exc:
            raise _provider_import_error(provider_config.package, provider) from exc

        return ChatAnthropic(
            model=resolved_config.default_model,
            api_key=resolved_config.llm_api_key,
            base_url=resolved_config.llm_base_url,
            **common,
        )

    if provider == "google_genai":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ModuleNotFoundError as exc:
            raise _provider_import_error(provider_config.package, provider) from exc

        return ChatGoogleGenerativeAI(
            model=resolved_config.default_model,
            google_api_key=resolved_config.llm_api_key,
            **common,
        )

    try:
        from langchain.chat_models import init_chat_model
    except ModuleNotFoundError as exc:
        raise _provider_import_error(provider_config.package, provider) from exc

    return init_chat_model(resolved_config.default_model, **common)
