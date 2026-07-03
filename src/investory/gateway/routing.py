"""Task routing helpers for the HTTP gateway."""

from __future__ import annotations

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
    INSTRUMENT_BRIEF_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK,
    TASKS,
)


TASK_ALIASES = {
    "qa": FINANCE_QA_TASK.name,
    "summary": LEARNING_MATERIAL_SUMMARY_TASK.name,
    "brief": INSTRUMENT_BRIEF_TASK.name,
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


def list_specs_by_tag(tag: str) -> list[TaskSpec]:
    """Return all TaskSpecs matching the given tag."""
    return [spec for spec in TASKS.values() if spec.tag == tag]


def list_specs_by_side_effect(level: str) -> list[TaskSpec]:
    """Return all TaskSpecs matching the given side_effect_level."""
    return [spec for spec in TASKS.values() if spec.side_effect_level == level]


def list_all_specs() -> list[TaskSpec]:
    """Return all TaskSpecs."""
    return list(TASKS.values())


def get_spec_metadata(task_name: str) -> dict:
    """Get governance metadata for a single task."""
    spec = TASKS.get(task_name)
    if spec is None:
        raise UnknownTaskTypeError(task_name)
    return {
        "name": spec.name,
        "side_effect_level": spec.side_effect_level,
        "tag": spec.tag,
        "desc": spec.desc,
    }


__all__ = [
    "TASK_ALIASES",
    "UnknownTaskTypeError",
    "resolve_task_name",
    "resolve_task_spec",
    "list_specs_by_tag",
    "list_specs_by_side_effect",
    "list_all_specs",
    "get_spec_metadata",
]
