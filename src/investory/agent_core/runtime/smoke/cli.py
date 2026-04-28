"""Unified smoke-test command for Investory agent runtime checks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from investory.agent_core.runtime.smoke.provider import (
    DEFAULT_PROMPT,
    run_provider_smoke,
)
from investory.agent_core.runtime.smoke.task import DEFAULT_TASK_NAME, run_task_smoke
from investory.agent_core.tasks import TASKS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Investory smoke checks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    provider_parser = subparsers.add_parser(
        "provider",
        help="Check configured LLM provider access.",
    )
    provider_parser.add_argument(
        "--check-config-only",
        action="store_true",
        help="Validate provider config without sending a model request.",
    )
    provider_parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt used for the provider smoke request.",
    )

    task_parser = subparsers.add_parser(
        "task",
        help="Run a registered task through the task executor.",
    )
    task_parser.add_argument(
        "--task",
        default=DEFAULT_TASK_NAME,
        choices=sorted(TASKS),
        help="Registered task name to run.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "provider":
        return run_provider_smoke(
            check_config_only=args.check_config_only,
            prompt=args.prompt,
        )

    if args.command == "task":
        return run_task_smoke(task_name=args.task)

    raise ValueError(f"Unsupported smoke command: {args.command}")
