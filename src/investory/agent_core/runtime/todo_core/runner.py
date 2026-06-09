import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter
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
RETRY_ATTEMPTS_EXHAUSTED_ERROR_TYPE = "retry_attempts_exhausted"

DEPENDENCY_FAILED_MESSAGE = "Task skipped because one or more dependencies did not succeed."
FAIL_FAST_STOPPED_MESSAGE = "Task skipped because fail_fast stopped further execution."
EXECUTOR_EXCEPTION_MESSAGE = "Task failed because the executor raised an exception."
INVALID_EXECUTOR_RESULT_MESSAGE = "Task failed because executor returned an invalid status."
MISSING_RESULT_MESSAGE = "Task has no execution result due to internal runner inconsistency."
RETRY_ATTEMPTS_EXHAUSTED_MESSAGE = (
    "Task was not resumed because its retry attempts were already exhausted."
)

TODO_EVENT_LAYER_STARTED = "todo.layer.started"
TODO_EVENT_TASK_STARTED = "todo.task.started"
TODO_EVENT_TASK_SUCCEEDED = "todo.task.succeeded"
TODO_EVENT_TASK_FAILED = "todo.task.failed"
TODO_EVENT_TASK_SKIPPED = "todo.task.skipped"
TODO_EVENT_TASK_RETRYING = "todo.task.retrying"


TodoTaskExecutor = Callable[[TodoTaskSpec], Awaitable[TodoTaskResult]]
TodoExecutionEventHandler = Callable[[str, dict[str, Any]], None]


class TodoExecutionRunner:
    def __init__(
        self,
        executor: TodoTaskExecutor,
        *,
        concurrency: int = DEFAULT_TODO_CONCURRENCY,
        max_retries: int = DEFAULT_TODO_MAX_RETRIES,
        event_handler: TodoExecutionEventHandler | None = None,
    ) -> None:
        if concurrency <= 0:
            raise ValueError("Todo runner concurrency must be greater than zero.")
        if max_retries < 0:
            raise ValueError("Todo runner max_retries must be zero or greater.")

        self._executor = executor
        self._concurrency = concurrency
        self._max_retries = max_retries
        self._event_handler = event_handler

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

        result_by_id = _build_resume_result_by_id(
            resume_state=resume_state,
            failure_policy=plan.failure_policy,
            max_retries=self._max_retries,
        )
        resume_attempts_by_id = _build_resume_attempts_by_id(resume_state)
        should_stop_after_failure = _should_stop_after_resume_failure(
            failure_policy=plan.failure_policy,
            result_by_id=result_by_id,
        )
        semaphore = asyncio.Semaphore(self._concurrency)

        for layer_index, layer in enumerate(layers):
            self._emit_event(
                TODO_EVENT_LAYER_STARTED,
                {
                    "layer_index": layer_index,
                    "task_ids": [task.id for task in layer],
                },
            )
            runnable_tasks: list[TodoTaskSpec] = []

            for task in layer:
                if task.id in result_by_id:
                    continue

                dependency_failure = _find_dependency_failure(task, result_by_id)
                if dependency_failure is not None:
                    result = _build_skipped_result(
                        task_id=task.id,
                        error_type=DEPENDENCY_FAILED_ERROR_TYPE,
                        message=DEPENDENCY_FAILED_MESSAGE,
                        details={"failed_dependency_task_id": dependency_failure},
                    )
                    result_by_id[task.id] = result
                    self._emit_task_result_event(task=task, result=result)
                    continue

                if should_stop_after_failure:
                    result = _build_skipped_result(
                        task_id=task.id,
                        error_type=FAIL_FAST_STOPPED_ERROR_TYPE,
                        message=FAIL_FAST_STOPPED_MESSAGE,
                    )
                    result_by_id[task.id] = result
                    self._emit_task_result_event(task=task, result=result)
                    continue

                previous_attempts = resume_attempts_by_id.get(task.id, 0)
                if not _has_attempts_remaining(
                    failure_policy=plan.failure_policy,
                    max_retries=self._max_retries,
                    previous_attempts=previous_attempts,
                ):
                    result = _build_failed_result(
                        task_id=task.id,
                        error_type=RETRY_ATTEMPTS_EXHAUSTED_ERROR_TYPE,
                        message=RETRY_ATTEMPTS_EXHAUSTED_MESSAGE,
                    )
                    result_by_id[task.id] = result
                    self._emit_task_result_event(task=task, result=result)
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
                        previous_attempts=resume_attempts_by_id.get(task.id, 0),
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
        previous_attempts: int = 0,
    ) -> TodoTaskResult:
        total_attempts = _get_total_attempt_budget(
            failure_policy=failure_policy,
            max_retries=self._max_retries,
        )
        remaining_attempts = max(total_attempts - previous_attempts, 0)

        for attempt in range(1, remaining_attempts + 1):
            absolute_attempt = previous_attempts + attempt
            result = await self._execute_once(
                task=task,
                semaphore=semaphore,
                attempt=absolute_attempt,
            )

            if result.status == TodoTaskStatus.SUCCEEDED:
                return result

            if (
                failure_policy == TodoFailurePolicy.RETRY_THEN_FAIL
                and result.status == TodoTaskStatus.FAILED
                and attempt < remaining_attempts
            ):
                self._emit_event(
                    TODO_EVENT_TASK_RETRYING,
                    {
                        "task_id": task.id,
                        "task_kind": task.kind.value,
                        "attempt": absolute_attempt,
                        "next_attempt": absolute_attempt + 1,
                        "max_attempts": total_attempts,
                        "error_type": _todo_result_error_type(result),
                    },
                )
                continue

            return result

        return _build_failed_result(
            task_id=task.id,
            error_type=RETRY_ATTEMPTS_EXHAUSTED_ERROR_TYPE,
            message=RETRY_ATTEMPTS_EXHAUSTED_MESSAGE,
        )

    async def _execute_once(
        self,
        *,
        task: TodoTaskSpec,
        semaphore: asyncio.Semaphore,
        attempt: int,
    ) -> TodoTaskResult:
        async with semaphore:
            started_at = perf_counter()
            self._emit_event(
                TODO_EVENT_TASK_STARTED,
                {
                    "task_id": task.id,
                    "task_kind": task.kind.value,
                    "depends_on": task.depends_on,
                    "attempt": attempt,
                },
            )
            try:
                result = await self._executor(task)
            except Exception as exc:
                result = _build_failed_result(
                    task_id=task.id,
                    error_type=EXECUTOR_EXCEPTION_ERROR_TYPE,
                    message=EXECUTOR_EXCEPTION_MESSAGE,
                    details={"exception_type": exc.__class__.__name__, "exception": str(exc)},
                )
            duration_ms = int((perf_counter() - started_at) * 1000)

        if result.id != task.id:
            result = _build_failed_result(
                task_id=task.id,
                error_type=INVALID_EXECUTOR_RESULT_ERROR_TYPE,
                message=INVALID_EXECUTOR_RESULT_MESSAGE,
                details={"reason": "result_id_mismatch", "executor_result_id": result.id},
            )
        elif result.status not in {
            TodoTaskStatus.SUCCEEDED,
            TodoTaskStatus.FAILED,
            TodoTaskStatus.SKIPPED,
        }:
            result = _build_failed_result(
                task_id=task.id,
                error_type=INVALID_EXECUTOR_RESULT_ERROR_TYPE,
                message=INVALID_EXECUTOR_RESULT_MESSAGE,
                details={
                    "reason": "invalid_result_status",
                    "executor_result_status": result.status.value,
                },
            )

        self._emit_task_result_event(
            task=task,
            result=result,
            duration_ms=duration_ms,
        )
        return result

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        if self._event_handler is None:
            return
        self._event_handler(event_name, payload)

    def _emit_task_result_event(
        self,
        *,
        task: TodoTaskSpec,
        result: TodoTaskResult,
        duration_ms: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "task_id": task.id,
            "task_kind": task.kind.value,
            "status": result.status.value,
            "duration_ms": duration_ms,
            "error_type": _todo_result_error_type(result),
            "stage": _todo_result_error_stage(result),
            "result_keys": _todo_result_keys(result),
        }
        if result.status == TodoTaskStatus.SUCCEEDED:
            self._emit_event(TODO_EVENT_TASK_SUCCEEDED, payload)
            return
        if result.status == TodoTaskStatus.SKIPPED:
            dependency_task_id = _todo_result_error_detail(
                result,
                "failed_dependency_task_id",
            )
            if isinstance(dependency_task_id, str):
                payload["failed_dependency_task_id"] = dependency_task_id
            self._emit_event(TODO_EVENT_TASK_SKIPPED, payload)
            return
        self._emit_event(TODO_EVENT_TASK_FAILED, payload)


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


def _build_resume_result_by_id(
    *,
    resume_state: TodoExecutionResumeState | None,
    failure_policy: TodoFailurePolicy,
    max_retries: int,
) -> dict[str, TodoTaskResult]:
    if resume_state is None:
        return {}

    result_by_id: dict[str, TodoTaskResult] = {}
    for task_id, result in resume_state.results_by_id.items():
        if result.status == TodoTaskStatus.SUCCEEDED:
            result_by_id[task_id] = result
            continue

        previous_attempts = resume_state.attempts_by_id.get(task_id, 0)
        if result.status == TodoTaskStatus.FAILED and not _has_attempts_remaining(
            failure_policy=failure_policy,
            max_retries=max_retries,
            previous_attempts=previous_attempts,
        ):
            result_by_id[task_id] = result

    return result_by_id


def _build_resume_attempts_by_id(
    resume_state: TodoExecutionResumeState | None,
) -> dict[str, int]:
    if resume_state is None:
        return {}
    return dict(resume_state.attempts_by_id)


def _has_attempts_remaining(
    *,
    failure_policy: TodoFailurePolicy,
    max_retries: int,
    previous_attempts: int,
) -> bool:
    return previous_attempts < _get_total_attempt_budget(
        failure_policy=failure_policy,
        max_retries=max_retries,
    )


def _get_total_attempt_budget(
    *,
    failure_policy: TodoFailurePolicy,
    max_retries: int,
) -> int:
    if failure_policy == TodoFailurePolicy.RETRY_THEN_FAIL:
        return 1 + max_retries
    return 1


def _should_stop_after_resume_failure(
    *,
    failure_policy: TodoFailurePolicy,
    result_by_id: dict[str, TodoTaskResult],
) -> bool:
    return (
        failure_policy == TodoFailurePolicy.FAIL_FAST
        and any(result.status == TodoTaskStatus.FAILED for result in result_by_id.values())
    )


def _todo_result_error_type(result: TodoTaskResult) -> str | None:
    if result.error is None:
        return None
    error_type = result.error.get("error_type")
    return error_type if isinstance(error_type, str) else None


def _todo_result_error_stage(result: TodoTaskResult) -> str | None:
    details = _todo_result_error_details(result)
    stage = details.get("stage")
    return stage if isinstance(stage, str) else None


def _todo_result_error_detail(result: TodoTaskResult, key: str) -> Any:
    return _todo_result_error_details(result).get(key)


def _todo_result_error_details(result: TodoTaskResult) -> dict[str, Any]:
    if result.error is None:
        return {}
    details = result.error.get("details")
    return details if isinstance(details, dict) else {}


def _todo_result_keys(result: TodoTaskResult) -> list[str]:
    if not isinstance(result.result, dict):
        return []
    return sorted(result.result)


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
