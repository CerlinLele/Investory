"""Task routing helpers for the HTTP gateway."""

from __future__ import annotations

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.tasks import TASKS


TASK_ALIASES = {
    "qa": "finance_qa",
    "summary": "learning_material_summary",
}


class UnknownTaskTypeError(ValueError):
    """Raised when a public task type cannot be resolved to a registered task."""

    def __init__(self, task_type: str) -> None:
        self.task_type = task_type
        known_task_types = sorted({*TASK_ALIASES, *TASKS})
        known = ", ".join(known_task_types)
        super().__init__(
            f"Unknown task type '{task_type}'. Expected one of: {known}."
        )


def resolve_task_name(task_type: str) -> str:
    """Resolve a public task type or internal task name to a registered task name."""

    normalized = task_type.strip()
    task_name = TASK_ALIASES.get(normalized, normalized)

    if task_name not in TASKS:
        raise UnknownTaskTypeError(task_type)

    return task_name


def resolve_task_spec(task_type: str) -> TaskSpec:
    """Resolve a public task type or internal task name to a TaskSpec."""

    return TASKS[resolve_task_name(task_type)]


__all__ = [
    "TASK_ALIASES",
    "UnknownTaskTypeError",
    "resolve_task_name",
    "resolve_task_spec",
]
