"""Minimal runtime entry point for Investory."""

from __future__ import annotations

from investory.config import load_config


def main() -> int:
    config = load_config()

    config.logs_dir.mkdir(parents=True, exist_ok=True)
    config.data_dir.mkdir(parents=True, exist_ok=True)

    print(f"{config.app_name} starting in {config.app_env} mode")
    print(f"llm_provider={config.llm_provider}")
    print(f"default_model={config.default_model}")
    print(f"logs_dir={config.logs_dir}")
    print(f"data_dir={config.data_dir}")
    print(f"mock_tools_enabled={config.mock_tools_enabled}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
