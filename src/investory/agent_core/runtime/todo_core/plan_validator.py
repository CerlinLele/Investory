from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investory.agent_core.contracts.todo_execution import TodoExecutionPlan


class TodoPlanValidationErrorCode(str, Enum):
    DUPLICATE_TASK_ID = "duplicate_task_id"
    UNKNOWN_DEPENDENCY = "unknown_dependency"
    SELF_DEPENDENCY = "self_dependency"
    CYCLE_DETECTED = "cycle_detected"
    EMPTY_DESCRIPTION = "empty_description"
    EMPTY_COMPLETION_CRITERIA = "empty_completion_criteria"


class TodoPlanValidationError(BaseModel):
    code: TodoPlanValidationErrorCode
    message: str
    task_id: str | None = None
    dependency_task_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TodoPlanValidationResult(BaseModel):
    ok: bool
    errors: list[TodoPlanValidationError] = Field(default_factory=list)


class TodoPlanValidationException(ValueError):
    def __init__(self, result: TodoPlanValidationResult) -> None:
        self.result = result
        super().__init__(self._build_message(result))

    @staticmethod
    def _build_message(result: TodoPlanValidationResult) -> str:
        if result.ok:
            return "Todo plan is valid."
        parts = [
            f"{error.code.value} (task_id={error.task_id}, dependency={error.dependency_task_id})"
            for error in result.errors
        ]
        return "Todo plan validation failed: " + "; ".join(parts)


def validate_todo_plan(plan: TodoExecutionPlan) -> TodoPlanValidationResult:
    errors: list[TodoPlanValidationError] = []

    tasks_by_id: dict[str, Any] = {}
    duplicate_ids: set[str] = set()
    for task in plan.tasks:
        if task.id in tasks_by_id:
            duplicate_ids.add(task.id)
            continue
        tasks_by_id[task.id] = task

    for duplicate_id in sorted(duplicate_ids):
        errors.append(
            TodoPlanValidationError(
                code=TodoPlanValidationErrorCode.DUPLICATE_TASK_ID,
                message="Task id must be unique within a todo plan.",
                task_id=duplicate_id,
            )
        )

    known_task_ids = set(tasks_by_id.keys())
    dependency_map: dict[str, list[str]] = {}

    for task in plan.tasks:
        if not task.description.strip():
            errors.append(
                TodoPlanValidationError(
                    code=TodoPlanValidationErrorCode.EMPTY_DESCRIPTION,
                    message="Task description must not be empty.",
                    task_id=task.id,
                )
            )

        completion_criteria = [item.strip() for item in task.completion_criteria]
        has_non_empty_completion_criteria = any(completion_criteria)
        if not has_non_empty_completion_criteria:
            errors.append(
                TodoPlanValidationError(
                    code=TodoPlanValidationErrorCode.EMPTY_COMPLETION_CRITERIA,
                    message="Task completion_criteria must contain at least one non-empty entry.",
                    task_id=task.id,
                )
            )

        if task.id in duplicate_ids:
            continue

        task_dependencies: list[str] = []
        for dependency_task_id in task.depends_on:
            if dependency_task_id == task.id:
                errors.append(
                    TodoPlanValidationError(
                        code=TodoPlanValidationErrorCode.SELF_DEPENDENCY,
                        message="Task must not depend on itself.",
                        task_id=task.id,
                        dependency_task_id=dependency_task_id,
                    )
                )
                continue

            if dependency_task_id not in known_task_ids:
                errors.append(
                    TodoPlanValidationError(
                        code=TodoPlanValidationErrorCode.UNKNOWN_DEPENDENCY,
                        message="Task dependency does not exist in the plan.",
                        task_id=task.id,
                        dependency_task_id=dependency_task_id,
                    )
                )
                continue

            task_dependencies.append(dependency_task_id)

        dependency_map[task.id] = task_dependencies

    cycle_path = _find_cycle_path(dependency_map)
    if cycle_path:
        errors.append(
            TodoPlanValidationError(
                code=TodoPlanValidationErrorCode.CYCLE_DETECTED,
                message="Cycle detected in task dependencies.",
                task_id=cycle_path[0],
                details={"cycle_path": cycle_path},
            )
        )

    return TodoPlanValidationResult(ok=not errors, errors=errors)


def ensure_valid_todo_plan(plan: TodoExecutionPlan) -> None:
    validation_result = validate_todo_plan(plan)
    if not validation_result.ok:
        raise TodoPlanValidationException(validation_result)


def _find_cycle_path(dependency_map: dict[str, list[str]]) -> list[str]:
    visit_state: dict[str, int] = {}
    path_stack: list[str] = []

    def dfs(task_id: str) -> list[str]:
        current_state = visit_state.get(task_id, 0)
        if current_state == 1:
            cycle_start_index = path_stack.index(task_id)
            return path_stack[cycle_start_index:] + [task_id]
        if current_state == 2:
            return []

        visit_state[task_id] = 1
        path_stack.append(task_id)
        for dependency_task_id in dependency_map.get(task_id, []):
            cycle = dfs(dependency_task_id)
            if cycle:
                return cycle
        path_stack.pop()
        visit_state[task_id] = 2
        return []

    for task_id in dependency_map:
        cycle = dfs(task_id)
        if cycle:
            return cycle
    return []
