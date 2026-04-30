"""FastAPI entry point for Investory."""

from __future__ import annotations

from fastapi import FastAPI

from investory.config import load_config
from investory.gateway.api import router as gateway_router


def create_app() -> FastAPI:
    """Create the Investory FastAPI application."""

    config = load_config()

    config.logs_dir.mkdir(parents=True, exist_ok=True)
    config.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title=config.app_name)
    app.state.config = config
    app.include_router(gateway_router)

    return app


app = create_app()


def main() -> int:
    config = app.state.config

    print(f"{config.app_name} starting in {config.app_env} mode")
    print(f"llm_provider={config.llm_provider}")
    print(f"default_model={config.default_model}")
    print(f"logs_dir={config.logs_dir}")
    print(f"data_dir={config.data_dir}")
    print(f"mock_tools_enabled={config.mock_tools_enabled}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
