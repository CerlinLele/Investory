import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoFailurePolicy,
    TodoTaskResult,
    TodoTaskSpec,
    TodoTaskStatus,
)
from investory.agent_core.runtime.todo_core.dependency_layers import (
    build_dependency_layers,
)
from investory.agent_core.runtime.todo_core.plan_validator import ensure_valid_todo_plan


DEFAULT_TODO_CONCURRENCY = 3
DEFAULT_TODO_MAX_RETRIES = 2

DEPENDENCY_FAILED_ERROR_TYPE = "dependency_failed"
FAIL_FAST_STOPPED_ERROR_TYPE = "fail_fast_stopped"
EXECUTOR_EXCEPTION_ERROR_TYPE = "executor_exception"
INVALID_EXECUTOR_RESULT_ERROR_TYPE = "invalid_executor_result"
MISSING_RESULT_ERROR_TYPE = "missing_result"

DEPENDENCY_FAILED_MESSAGE = "Task skipped because one or more dependencies did not succeed."
FAIL_FAST_STOPPED_MESSAGE = "Task skipped because fail_fast stopped further execution."
EXECUTOR_EXCEPTION_MESSAGE = "Task failed because the executor raised an exception."
INVALID_EXECUTOR_RESULT_MESSAGE = "Task failed because executor returned an invalid status."
MISSING_RESULT_MESSAGE = "Task has no execution result due to internal runner inconsistency."


TodoTaskExecutor = Callable[[TodoTaskSpec], Awaitable[TodoTaskResult]]


class TodoExecutionRunner:
    def __init__(
        self,
        executor: TodoTaskExecutor,
        *,
        concurrency: int = DEFAULT_TODO_CONCURRENCY,
        max_retries: int = DEFAULT_TODO_MAX_RETRIES,
    ) -> None:
        if concurrency <= 0:
            raise ValueError("Todo runner concurrency must be greater than zero.")
        if max_retries < 0:
            raise ValueError("Todo runner max_retries must be zero or greater.")

        self._executor = executor
        self._concurrency = concurrency
        self._max_retries = max_retries

    async def run(
        self,
        plan: TodoExecutionPlan,
        *,
        resume_state: TodoExecutionResumeState | None = None,
    ) -> list[TodoTaskResult]:
        ensure_valid_todo_plan(plan)
        if resume_state is not None:
            _ensure_resume_state_matches_plan(plan=plan, resume_state=resume_state)

        layers = build_dependency_layers(plan)

        result_by_id = _build_succeeded_resume_results_by_id(resume_state)
        should_stop_after_failure = False
        semaphore = asyncio.Semaphore(self._concurrency)

        for layer in layers:
            runnable_tasks: list[TodoTaskSpec] = []

            for task in layer:
                if task.id in result_by_id:
                    continue

                dependency_failure = _find_dependency_failure(task, result_by_id)
                if dependency_failure is not None:
                    result_by_id[task.id] = _build_skipped_result(
                        task_id=task.id,
                        error_type=DEPENDENCY_FAILED_ERROR_TYPE,
                        message=DEPENDENCY_FAILED_MESSAGE,
                        details={"failed_dependency_task_id": dependency_failure},
                    )
                    continue

                if should_stop_after_failure:
                    result_by_id[task.id] = _build_skipped_result(
                        task_id=task.id,
                        error_type=FAIL_FAST_STOPPED_ERROR_TYPE,
                        message=FAIL_FAST_STOPPED_MESSAGE,
                    )
                    continue

                runnable_tasks.append(task)

            if not runnable_tasks:
                continue

            layer_results = await asyncio.gather(
                *[
                    self._execute_with_retries(
                        task=task,
                        failure_policy=plan.failure_policy,
                        semaphore=semaphore,
                    )
                    for task in runnable_tasks
                ]
            )

            for result in layer_results:
                result_by_id[result.id] = result

            if (
                plan.failure_policy == TodoFailurePolicy.FAIL_FAST
                and any(result.status == TodoTaskStatus.FAILED for result in layer_results)
            ):
                should_stop_after_failure = True

        return [
            result_by_id.get(task.id)
            or _build_skipped_result(
                task_id=task.id,
                error_type=MISSING_RESULT_ERROR_TYPE,
                message=MISSING_RESULT_MESSAGE,
            )
            for task in plan.tasks
        ]

    async def _execute_with_retries(
        self,
        *,
        task: TodoTaskSpec,
        failure_policy: TodoFailurePolicy,
        semaphore: asyncio.Semaphore,
    ) -> TodoTaskResult:
        total_attempts = 1
        if failure_policy == TodoFailurePolicy.RETRY_THEN_FAIL:
            total_attempts += self._max_retries

        for attempt in range(1, total_attempts + 1):
            result = await self._execute_once(task=task, semaphore=semaphore)

            if result.status == TodoTaskStatus.SUCCEEDED:
                return result

            if (
                failure_policy == TodoFailurePolicy.RETRY_THEN_FAIL
                and result.status == TodoTaskStatus.FAILED
                and attempt < total_attempts
            ):
                continue

            return result

        return _build_failed_result(
            task_id=task.id,
            error_type=EXECUTOR_EXCEPTION_ERROR_TYPE,
            message=EXECUTOR_EXCEPTION_MESSAGE,
            details={"reason": "retry_loop_exhausted_without_terminal_result"},
        )

    async def _execute_once(
        self,
        *,
        task: TodoTaskSpec,
        semaphore: asyncio.Semaphore,
    ) -> TodoTaskResult:
        async with semaphore:
            try:
                result = await self._executor(task)
            except Exception as exc:
                return _build_failed_result(
                    task_id=task.id,
                    error_type=EXECUTOR_EXCEPTION_ERROR_TYPE,
                    message=EXECUTOR_EXCEPTION_MESSAGE,
                    details={"exception_type": exc.__class__.__name__, "exception": str(exc)},
                )

        if result.id != task.id:
            return _build_failed_result(
                task_id=task.id,
                error_type=INVALID_EXECUTOR_RESULT_ERROR_TYPE,
                message=INVALID_EXECUTOR_RESULT_MESSAGE,
                details={"reason": "result_id_mismatch", "executor_result_id": result.id},
            )

        if result.status not in {
            TodoTaskStatus.SUCCEEDED,
            TodoTaskStatus.FAILED,
            TodoTaskStatus.SKIPPED,
        }:
            return _build_failed_result(
                task_id=task.id,
                error_type=INVALID_EXECUTOR_RESULT_ERROR_TYPE,
                message=INVALID_EXECUTOR_RESULT_MESSAGE,
                details={
                    "reason": "invalid_result_status",
                    "executor_result_status": result.status.value,
                },
            )

        return result


def _find_dependency_failure(
    task: TodoTaskSpec,
    result_by_id: dict[str, TodoTaskResult],
) -> str | None:
    for dependency_task_id in task.depends_on:
        dependency_result = result_by_id.get(dependency_task_id)
        if dependency_result is None:
            return dependency_task_id
        if dependency_result.status != TodoTaskStatus.SUCCEEDED:
            return dependency_task_id
    return None


def _ensure_resume_state_matches_plan(
    *,
    plan: TodoExecutionPlan,
    resume_state: TodoExecutionResumeState,
) -> None:
    if resume_state.plan != plan:
        raise ValueError("Todo runner resume_state.plan must match the plan being run.")


def _build_succeeded_resume_results_by_id(
    resume_state: TodoExecutionResumeState | None,
) -> dict[str, TodoTaskResult]:
    if resume_state is None:
        return {}

    return {
        task_id: result
        for task_id, result in resume_state.results_by_id.items()
        if result.status == TodoTaskStatus.SUCCEEDED
    }


def _build_failed_result(
    *,
    task_id: str,
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> TodoTaskResult:
    return TodoTaskResult(
        id=task_id,
        status=TodoTaskStatus.FAILED,
        error={
            "error_type": error_type,
            "message": message,
            "details": details or {},
        },
    )


def _build_skipped_result(
    *,
    task_id: str,
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> TodoTaskResult:
    return TodoTaskResult(
        id=task_id,
        status=TodoTaskStatus.SKIPPED,
        error={
            "error_type": error_type,
            "message": message,
            "details": details or {},
        },
    )
