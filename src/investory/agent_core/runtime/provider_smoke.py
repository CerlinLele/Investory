"""Manual smoke check for the configured LLM provider."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from investory.agent_core.runtime.model_factory import create_chat_model
from investory.config import AppConfig, load_config


DEFAULT_PROMPT = "用一句话回答：Investory 是什么？"


def _format_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    return str(content)


def _print_config_summary(config: AppConfig) -> None:
    provider_config = config.llm_provider_config

    print(f"provider={config.llm_provider}")
    print(f"model={config.default_model}")
    print(f"base_url_env={provider_config.base_url_env}")
    print(f"base_url={config.llm_base_url}")
    print(f"api_key_env={provider_config.api_key_env}")
    print(f"api_key_configured={bool(config.llm_api_key)}")
    print(f"temperature={config.llm_temperature}")
    print(f"max_retries={config.llm_max_retries}")


def run_provider_smoke(*, check_config_only: bool = False, prompt: str = DEFAULT_PROMPT) -> int:
    """Run a minimal provider check and return a process exit code."""

    config = load_config()
    _print_config_summary(config)

    if not config.llm_api_key:
        print(f"error=Missing API key env: {config.llm_provider_config.api_key_env}")
        return 2

    if check_config_only:
        return 0

    try:
        model = create_chat_model(config)
        response = model.invoke(prompt)
    except Exception as exc:
        print(f"error_type={type(exc).__name__}")
        print(f"error_message={exc}")
        return 1

    print("response:")
    print(_format_content(response.content))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal smoke check for the configured LLM provider.",
    )
    parser.add_argument(
        "--check-config-only",
        action="store_true",
        help="Validate provider config without sending a model request.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt used for the smoke request.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_provider_smoke(
        check_config_only=args.check_config_only,
        prompt=args.prompt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
