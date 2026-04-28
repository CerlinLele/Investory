"""Configuration primitives for the Investory app."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppConfig:
    """Minimal runtime settings shared across the project."""

    app_name: str = "Investory"
    app_env: str = "dev"
    logs_dir: Path = PROJECT_ROOT / "logs"
    data_dir: Path = PROJECT_ROOT / "data"
    llm_provider: str = "openai"
    default_model: str = "gpt-5.4-mini"
    mock_tools_enabled: bool = True


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    """Load the minimal app config from environment variables."""

    return AppConfig(
        app_name=getenv("INVESTORY_APP_NAME", "Investory"),
        app_env=getenv("INVESTORY_APP_ENV", "dev"),
        logs_dir=Path(getenv("INVESTORY_LOGS_DIR", str(PROJECT_ROOT / "logs"))),
        data_dir=Path(getenv("INVESTORY_DATA_DIR", str(PROJECT_ROOT / "data"))),
        llm_provider=getenv("INVESTORY_LLM_PROVIDER", "openai"),
        default_model=getenv("INVESTORY_DEFAULT_MODEL", "gpt-5.4-mini"),
        mock_tools_enabled=_as_bool(
            getenv("INVESTORY_MOCK_TOOLS_ENABLED"),
            default=True,
        ),
    )
