"""Manual smoke check for the configured task executor."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.tasks import TASKS


DEFAULT_TASK_NAME = "finance_qa"

DEFAULT_PAYLOADS = {
    "finance_qa": {
        "material_text": (
            "Maximum drawdown is the largest decline from a peak to a trough "
            "over a period of time."
        ),
        "question": "What does maximum drawdown mean, and why is it important?",
    },
    "learning_material_summary": {
        "material_text": (
            "Maximum drawdown is the largest decline from a peak to a trough "
            "over a period of time. It helps investors understand downside risk."
        ),
    },
}


def _print_result(result: TaskResult) -> None:
    print(result.model_dump_json(indent=2))


def run_task_smoke(
    *,
    task_name: str = DEFAULT_TASK_NAME,
    executor: TaskExecutor | None = None,
) -> int:
    spec = TASKS.get(task_name)
    if spec is None:
        known_tasks = ", ".join(sorted(TASKS))
        print(f"error=Unknown task: {task_name}")
        print(f"known_tasks={known_tasks}")
        return 2

    resolved_executor = executor or TaskExecutor()
    result = resolved_executor.run(spec, DEFAULT_PAYLOADS[task_name])
    _print_result(result)
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a minimal smoke check for a registered Investory task.",
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK_NAME,
        choices=sorted(TASKS),
        help="Registered task name to run.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_task_smoke(task_name=args.task)


if __name__ == "__main__":
    raise SystemExit(main())
