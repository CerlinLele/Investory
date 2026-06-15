"""Configuration primitives for the Investory app."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import environ, getenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LLM_PROVIDER = "openai"


@dataclass(frozen=True, slots=True)
class LLMProviderConfig:
    """Static metadata for a supported LLM provider."""

    name: str
    package: str
    default_model: str
    default_base_url: str
    base_url_env: str
    api_key_env: str


LLM_PROVIDERS: dict[str, LLMProviderConfig] = {
    "openai": LLMProviderConfig(
        name="openai",
        package="langchain-openai",
        default_model="gpt-5.4-mini",
        default_base_url="https://api.openai.com/v1",
        base_url_env="OPENAI_BASE_URL",
        api_key_env="OPENAI_API_KEY",
    ),
    "anthropic": LLMProviderConfig(
        name="anthropic",
        package="langchain-anthropic",
        default_model="claude-sonnet-4-20250514",
        default_base_url="https://api.anthropic.com",
        base_url_env="ANTHROPIC_BASE_URL",
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "google_genai": LLMProviderConfig(
        name="google_genai",
        package="langchain-google-genai",
        default_model="gemini-2.5-flash",
        default_base_url="https://generativelanguage.googleapis.com",
        base_url_env="GOOGLE_BASE_URL",
        api_key_env="GOOGLE_API_KEY",
    ),
}


@dataclass(slots=True)
class AppConfig:
    """Minimal runtime settings shared across the project."""

    app_name: str = "Investory"
    app_env: str = "dev"
    logs_dir: Path = PROJECT_ROOT / "logs"
    data_dir: Path = PROJECT_ROOT / "data"
    llm_provider: str = DEFAULT_LLM_PROVIDER
    default_model: str = "gpt-5.4-mini"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_temperature: float = 0
    llm_max_retries: int = 2
    llm_provider_config: LLMProviderConfig = field(
        default_factory=lambda: LLM_PROVIDERS[DEFAULT_LLM_PROVIDER],
    )
    mock_tools_enabled: bool = True
    log_level: str = "INFO"


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _as_float(value: str | None, *, default: float) -> float:
    if value is None:
        return default

    return float(value)


def _as_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default

    return int(value)


def _clean_env_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]

    return cleaned


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in environ:
            continue

        environ[key] = _clean_env_value(value)


def get_llm_provider_config(provider: str) -> LLMProviderConfig:
    """Return provider metadata or fail with a clear supported-provider list."""

    normalized = provider.strip().lower()
    if normalized in LLM_PROVIDERS:
        return LLM_PROVIDERS[normalized]

    supported = ", ".join(sorted(LLM_PROVIDERS))
    raise ValueError(f"Unsupported LLM provider '{provider}'. Supported: {supported}.")


def load_config(*, env_file: Path | None = PROJECT_ROOT / ".env") -> AppConfig:
    """Load the minimal app config from environment variables."""

    if env_file is not None:
        _load_env_file(env_file)

    provider = getenv("INVESTORY_LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
    provider_config = get_llm_provider_config(provider)

    return AppConfig(
        app_name=getenv("INVESTORY_APP_NAME", "Investory"),
        app_env=getenv("INVESTORY_APP_ENV", "dev"),
        logs_dir=Path(getenv("INVESTORY_LOGS_DIR", str(PROJECT_ROOT / "logs"))),
        data_dir=Path(getenv("INVESTORY_DATA_DIR", str(PROJECT_ROOT / "data"))),
        llm_provider=provider_config.name,
        default_model=getenv("INVESTORY_DEFAULT_MODEL", provider_config.default_model),
        llm_base_url=getenv(provider_config.base_url_env, provider_config.default_base_url),
        llm_api_key=getenv(provider_config.api_key_env),
        llm_temperature=_as_float(getenv("INVESTORY_LLM_TEMPERATURE"), default=0),
        llm_max_retries=_as_int(getenv("INVESTORY_LLM_MAX_RETRIES"), default=2),
        llm_provider_config=provider_config,
        mock_tools_enabled=_as_bool(
            getenv("INVESTORY_MOCK_TOOLS_ENABLED"),
            default=True,
        ),
        log_level=getenv("INVESTORY_LOG_LEVEL", "INFO").strip().upper(),
    )
