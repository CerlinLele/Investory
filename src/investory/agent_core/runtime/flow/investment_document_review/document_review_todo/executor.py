"""Todo plan execution, resume state management, and execution logging."""

import asyncio
import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewState,
)
from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionResumeState,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    InvestmentDocumentReviewTodoResumeStore,
    SYNTHESIZE_REVIEW_TASK_ID,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.runtime.todo_core.runner import (
    TODO_EVENT_LAYER_STARTED,
    TODO_EVENT_TASK_FAILED,
    TODO_EVENT_TASK_RETRYING,
    TODO_EVENT_TASK_SKIPPED,
    TODO_EVENT_TASK_STARTED,
    TODO_EVENT_TASK_SUCCEEDED,
    TodoExecutionRunner,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)

from .payload import (
    build_review_todo_analyze_payload,
    build_review_todo_dependency_results,
    build_review_todo_extract_payload,
    build_review_todo_synthesize_payload,
)
from .plan_builder import should_use_chunk_review
from .summary import find_succeeded_todo_result

FLOW_LOGGER_NAME = "investory.agent_core.runtime.flow.investment_document_review.document_review_flow"
logger = logging.getLogger(FLOW_LOGGER_NAME)


def _todo_task_skip_reason(error_type: Any) -> str | None:
    if not isinstance(error_type, str):
        return None
    return error_type


def _count_todo_results_by_status(
    todo_results: list[TodoTaskResult],
) -> dict[TodoTaskStatus, int]:
    counts = {
        TodoTaskStatus.SUCCEEDED: 0,
        TodoTaskStatus.FAILED: 0,
        TodoTaskStatus.SKIPPED: 0,
    }
    for result in todo_results:
        if result.status in counts:
            counts[result.status] += 1
    return counts


def _build_review_todo_runner_event_handler(
    *,
    session_id: str | None,
) -> Callable[[str, dict[str, Any]], None]:
    def handle_event(event_name: str, payload: dict[str, Any]) -> None:
        if event_name == TODO_EVENT_LAYER_STARTED:
            logger.debug(
                "investment_document_review.todo_layer.started session_id=%s layer_index=%s task_ids=%s",
                session_id,
                payload.get("layer_index"),
                ",".join(payload.get("task_ids", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_STARTED:
            logger.info(
                "investment_document_review.todo_task.started session_id=%s task_id=%s task_kind=%s depends_on=%s attempt=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                ",".join(payload.get("depends_on", [])),
                payload.get("attempt"),
            )
            return

        if event_name == TODO_EVENT_TASK_RETRYING:
            logger.info(
                "investment_document_review.todo_task.retrying session_id=%s task_id=%s task_kind=%s attempt=%s next_attempt=%s max_attempts=%s error_type=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("attempt"),
                payload.get("next_attempt"),
                payload.get("max_attempts"),
                payload.get("error_type"),
            )
            return

        if event_name == TODO_EVENT_TASK_SUCCEEDED:
            logger.info(
                "investment_document_review.todo_task.succeeded session_id=%s task_id=%s task_kind=%s duration_ms=%s result_keys=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                ",".join(payload.get("result_keys", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_FAILED:
            logger.warning(
                "investment_document_review.todo_task.failed session_id=%s task_id=%s task_kind=%s duration_ms=%s error_type=%s stage=%s result_keys=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                payload.get("error_type"),
                payload.get("stage"),
                ",".join(payload.get("result_keys", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_SKIPPED:
            reason = _todo_task_skip_reason(payload.get("error_type"))
            logger.info(
                "investment_document_review.todo_task.skipped session_id=%s task_id=%s task_kind=%s duration_ms=%s reason=%s stage=%s failed_dependency_task_id=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                reason,
                payload.get("stage"),
                payload.get("failed_dependency_task_id"),
            )

    return handle_event


def _log_review_todo_execution_started(
    *,
    session_id: str | None,
    todo_plan,
    resume_state: TodoExecutionResumeState | None,
) -> None:
    logger.info(
        "investment_document_review.todo_execution.started session_id=%s "
        "task_count=%s resume_task_count=%s failure_policy=%s",
        session_id,
        len(todo_plan.tasks),
        len(resume_state.results_by_id) if resume_state is not None else 0,
        todo_plan.failure_policy.value,
    )


def _log_review_todo_execution_completed(
    *,
    session_id: str | None,
    todo_results: list[TodoTaskResult],
    duration_ms: int,
    synthesis_produced: bool,
) -> None:
    counts = _count_todo_results_by_status(todo_results)
    logger.info(
        "investment_document_review.todo_execution.completed session_id=%s "
        "succeeded_count=%s failed_count=%s skipped_count=%s duration_ms=%s "
        "synthesis_produced=%s",
        session_id,
        counts[TodoTaskStatus.SUCCEEDED],
        counts[TodoTaskStatus.FAILED],
        counts[TodoTaskStatus.SKIPPED],
        duration_ms,
        str(synthesis_produced).lower(),
    )


def _load_todo_resume_state(
    state: InvestmentDocumentReviewState,
    todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None,
) -> TodoExecutionResumeState | None:
    if todo_resume_store is None:
        return None

    if state.session_id is None:
        return None

    if state.todo_plan is None:
        raise RuntimeError("Document review flow has no To-Do plan to resume.")

    resume_state = todo_resume_store.load_resume_state(
        session_id=state.session_id,
        plan=state.todo_plan,
    )
    if resume_state is not None:
        logger.info(
            "investment_document_review.todo_resume.loaded session_id=%s "
            "resumed_result_count=%s attempt_count=%s",
            state.session_id,
            len(resume_state.results_by_id),
            len(resume_state.attempts_by_id),
        )
    return resume_state


def _save_todo_resume_state(
    *,
    state: InvestmentDocumentReviewState,
    todo_results: list[TodoTaskResult],
    previous_resume_state: TodoExecutionResumeState | None,
    todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None,
) -> None:
    if todo_resume_store is None:
        return

    if state.session_id is None:
        return

    if state.todo_plan is None:
        raise RuntimeError("Document review flow has no To-Do plan to persist.")

    todo_resume_store.save_resume_state(
        session_id=state.session_id,
        plan=state.todo_plan,
        results=todo_results,
        previous_resume_state=previous_resume_state,
    )
    logger.info(
        "investment_document_review.todo_resume.saved session_id=%s "
        "saved_result_count=%s",
        state.session_id,
        len(todo_results),
    )


def _build_todo_execution_runner(
    state: InvestmentDocumentReviewState,
    executor: TaskExecutor,
    *,
    resume_state: TodoExecutionResumeState | None = None,
) -> TodoExecutionRunner:
    executed_results_by_id = {result.id: result for result in state.todo_results}
    if resume_state is not None:
        executed_results_by_id.update(resume_state.results_by_id)

    async def execute(task) -> TodoTaskResult:
        result = await _execute_review_todo_task(
            state=state,
            task=task,
            executor=executor,
            executed_results_by_id=executed_results_by_id,
        )
        executed_results_by_id[result.id] = result
        return result

    return TodoExecutionRunner(
        execute,
        event_handler=_build_review_todo_runner_event_handler(
            session_id=state.session_id,
        ),
    )


async def _execute_review_todo_task(
    *,
    state,
    task,
    executor: TaskExecutor,
    executed_results_by_id: dict[str, TodoTaskResult],
) -> TodoTaskResult:
    try:
        spec, payload = _build_review_todo_task_execution(
            state=state,
            task=task,
            executed_results_by_id=executed_results_by_id,
        )
    except RuntimeError as exc:
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "todo_task_payload_not_supported",
                "message": str(exc),
                "details": {"task_kind": task.kind.value},
            },
        )

    result = await asyncio.to_thread(executor.run, spec, payload)
    if result.ok:
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.SUCCEEDED,
            result=result.result,
        )

    return TodoTaskResult(
        id=task.id,
        status=TodoTaskStatus.FAILED,
        error={
            "error_type": "todo_task_execution_failed",
            "message": (
                result.error.user_safe_message
                if result.error is not None
                else "The To-Do task failed to run."
            ),
            "details": {
                "task_name": spec.name,
                "task_kind": task.kind.value,
                "stage": result.error.stage if result.error is not None else None,
                "debug_message": (
                    result.error.debug_message if result.error is not None else None
                ),
            },
        },
    )


def _build_review_todo_task_execution(
    *,
    state: InvestmentDocumentReviewState,
    task,
    executed_results_by_id: dict[str, TodoTaskResult],
) -> tuple[Any, dict[str, Any]]:
    if state.document_type is None:
        raise RuntimeError("Document review flow has no classified document type.")

    if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT:
        return (
            INVESTMENT_DOCUMENT_EXTRACT_TASK,
            build_review_todo_extract_payload(state=state, task=task),
        )

    if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE:
        return (
            INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
            build_review_todo_synthesize_payload(
                state=state,
                executed_results_by_id=executed_results_by_id,
            ),
        )

    if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE:
        return (
            INVESTMENT_DOCUMENT_ANALYZE_TASK,
            build_review_todo_analyze_payload(
                state=state,
                task=task,
                dependency_results=build_review_todo_dependency_results(
                    task=task,
                    executed_results_by_id=executed_results_by_id,
                ),
            ),
        )

    raise RuntimeError(f"Unsupported investment document To-Do task kind: {task.kind.value}")


def execute_review_todo_plan(
    state: InvestmentDocumentReviewState,
    executor: TaskExecutor,
    todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None,
    runner_factory: Callable[
        [InvestmentDocumentReviewState, TaskExecutor, TodoExecutionResumeState | None],
        TodoExecutionRunner,
    ] | None = None,
) -> dict[str, Any]:
    if state.todo_plan is None:
        raise RuntimeError("Document review flow has no To-Do plan to execute.")

    resume_state = _load_todo_resume_state(state, todo_resume_store)
    started_at = perf_counter()
    _log_review_todo_execution_started(
        session_id=state.session_id,
        todo_plan=state.todo_plan,
        resume_state=resume_state,
    )
    if runner_factory is None:
        runner = _build_todo_execution_runner(
            state,
            executor,
            resume_state=resume_state,
        )
    else:
        runner = runner_factory(state, executor, resume_state)
    todo_results = asyncio.run(
        runner.run(state.todo_plan, resume_state=resume_state)
    )
    synthesize_result = find_succeeded_todo_result(
        todo_results,
        SYNTHESIZE_REVIEW_TASK_ID,
    )
    _log_review_todo_execution_completed(
        session_id=state.session_id,
        todo_results=todo_results,
        duration_ms=int((perf_counter() - started_at) * 1000),
        synthesis_produced=synthesize_result is not None,
    )
    _save_todo_resume_state(
        state=state,
        todo_results=todo_results,
        previous_resume_state=resume_state,
        todo_resume_store=todo_resume_store,
    )
    update: dict[str, Any] = {"todo_results": todo_results}
    if synthesize_result is not None:
        update["output"] = TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            result=synthesize_result.result,
        )
    elif should_use_chunk_review(state):
        from investory.agent_core.contracts.result_types import normalize_task_error
        
        update["output"] = TaskResult(
            ok=False,
            task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            error=normalize_task_error(
                RuntimeError("Chunk-based document review did not produce synthesis."),
                stage="output_validation",
            ),
        )
    return update