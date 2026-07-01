import asyncio
import logging
import re
from collections.abc import Callable
from time import perf_counter
from typing import TYPE_CHECKING, Any

from investory.agent_core.contracts.investment_document_review_state import (
    ANALYZE_FOCUS_FIELD,
    DOCUMENT_TEXT_FIELD,
    EXTRACT_FOCUS_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.result_types import TaskResult, normalize_task_error
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    AGGREGATE_ANALYZE_TASK_ID,
    ANALYZE_TASK_ID_PREFIX,
    CHUNK_COUNT_FIELD,
    CHUNK_EXTRACT_TASK_ID_PREFIX,
    CHUNK_INDEX_FIELD,
    CHUNK_REVIEW_SCOPE,
    CHUNK_REVIEW_SCOPE_FIELD,
    COMPLETED_TODO_RESULT_STATUSES,
    FULL_DOCUMENT_EXTRACT_TASK_ID,
    FULL_DOCUMENT_REVIEW_SCOPE,
    SYNTHESIZE_REVIEW_TASK_ID,
    InvestmentDocumentReviewTodoResumeStore,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_router import (
    InvestmentDocumentReviewRouter,
)
from investory.agent_core.runtime.flow.investment_document_review.document_chunker import (
    split_into_chunks,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeInput,
    InvestmentDocumentReviewExtractInput,
    InvestmentDocumentReviewSynthesizeInput,
    InvestmentDocumentReviewTodoSummary,
    InvestmentDocumentReviewTodoTaskSummary,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.runtime.todo_core.plan_validator import (
    TodoPlanValidationException,
    ensure_valid_todo_plan,
)
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
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def should_use_chunk_review(state: InvestmentDocumentReviewState) -> bool:
    return len(state.document_chunks or []) > 1


def should_use_code_built_plan(state: InvestmentDocumentReviewState) -> bool:
    if state.document_type is None:
        return False
    if state.document_type == InvestmentDocumentType.UNKNOWN:
        return False
    return state.review_framework is not None


def is_chunked_document(state: InvestmentDocumentReviewState) -> bool:
    return len(state.document_chunks or []) > 1


def _normalize_todo_task_id_fragment(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "dimension"


def _string_list_from_result(result_payload: dict[str, Any], key: str) -> list[str]:
    value = result_payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_from_result(result_payload: dict[str, Any], key: str) -> str | None:
    value = result_payload.get(key)
    if isinstance(value, str):
        return value
    return None


def _todo_result_error_message(result: TodoTaskResult) -> str | None:
    if result.error is None:
        return None
    message = result.error.get("message")
    if isinstance(message, str):
        return message
    return None


def _todo_incomplete_review_note(
    *,
    result: TodoTaskResult,
    task_title: str | None,
) -> str:
    task_label = task_title or result.id
    reason = _todo_result_error_message(result)
    if reason:
        return f"{task_label} ({result.id}) did not complete: {reason}"
    return f"{task_label} ({result.id}) did not complete with status {result.status.value}."


def _build_completed_todo_results(
    todo_plan: TodoExecutionPlan,
    results_by_id: dict[str, TodoTaskResult],
) -> list[TodoTaskResult]:
    completed_results_by_id = {
        result.id: result
        for result in results_by_id.values()
        if result.status in COMPLETED_TODO_RESULT_STATUSES
    }
    planned_task_ids = [task.id for task in todo_plan.tasks]
    ordered_results = [
        completed_results_by_id[task_id]
        for task_id in planned_task_ids
        if task_id in completed_results_by_id
    ]
    ordered_results.extend(
        result
        for task_id, result in completed_results_by_id.items()
        if task_id not in planned_task_ids
    )
    return ordered_results


def _find_succeeded_todo_result(
    todo_results: list[TodoTaskResult],
    task_id: str,
) -> TodoTaskResult | None:
    for result in todo_results:
        if result.id == task_id and result.status == TodoTaskStatus.SUCCEEDED:
            return result
    return None


def _build_review_todo_summary(
    *,
    todo_plan: TodoExecutionPlan,
    completed_results: list[TodoTaskResult],
) -> InvestmentDocumentReviewTodoSummary:
    tasks_by_id = {task.id: task for task in todo_plan.tasks}
    succeeded_task_ids: list[str] = []
    failed_task_ids: list[str] = []
    skipped_task_ids: list[str] = []
    extracted_facts: list[str] = []
    risk_findings: list[str] = []
    information_gaps: list[str] = []
    boundary_notes: list[str] = []
    task_summaries: list[InvestmentDocumentReviewTodoTaskSummary] = []

    for result in completed_results:
        task = tasks_by_id.get(result.id)
        if result.status == TodoTaskStatus.SUCCEEDED:
            succeeded_task_ids.append(result.id)
            result_payload = result.result or {}
            extracted_facts.extend(_string_list_from_result(result_payload, "extracted_facts"))
            risk_findings.extend(_string_list_from_result(result_payload, "risk_findings"))
            information_gaps.extend(
                _string_list_from_result(result_payload, "information_gaps")
            )
            boundary_notes.extend(_string_list_from_result(result_payload, "boundary_notes"))
            summary = _string_from_result(result_payload, "summary")
        elif result.status == TodoTaskStatus.FAILED:
            failed_task_ids.append(result.id)
            summary = _todo_result_error_message(result)
            information_gaps.append(
                _todo_incomplete_review_note(
                    result=result,
                    task_title=task.title if task is not None else None,
                )
            )
        else:
            skipped_task_ids.append(result.id)
            summary = _todo_result_error_message(result)
            boundary_notes.append(
                _todo_incomplete_review_note(
                    result=result,
                    task_title=task.title if task is not None else None,
                )
            )

        task_summaries.append(
            InvestmentDocumentReviewTodoTaskSummary(
                task_id=result.id,
                task_title=task.title if task is not None else None,
                task_kind=task.kind if task is not None else None,
                status=result.status,
                summary=summary,
            )
        )

    return InvestmentDocumentReviewTodoSummary(
        plan_summary=todo_plan.summary,
        planned_task_count=len(todo_plan.tasks),
        completed_task_count=len(completed_results),
        succeeded_task_ids=succeeded_task_ids,
        failed_task_ids=failed_task_ids,
        skipped_task_ids=skipped_task_ids,
        extracted_facts=extracted_facts,
        risk_findings=risk_findings,
        information_gaps=information_gaps,
        boundary_notes=boundary_notes,
        task_summaries=task_summaries,
    )


def _build_review_task_status_summary(
    *,
    review_summary: InvestmentDocumentReviewTodoSummary,
) -> list[str]:
    status_summaries: list[str] = []
    for summary in review_summary.task_summaries:
        parts = [summary.task_id, summary.status.value]
        if summary.summary:
            parts.append(summary.summary)
        status_summaries.append(" | ".join(parts))
    return status_summaries


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


def _log_review_todo_plan_generated(
    *,
    session_id: str | None,
    todo_plan: TodoExecutionPlan,
    document_type: InvestmentDocumentType | None,
    chunk_count: int,
) -> None:
    logger.info(
        "investment_document_review.todo_plan.generated session_id=%s document_type=%s "
        "chunk_count=%s task_count=%s failure_policy=%s summary=%s",
        session_id,
        document_type.value if document_type is not None else None,
        chunk_count,
        len(todo_plan.tasks),
        todo_plan.failure_policy.value,
        todo_plan.summary,
    )
    for task in todo_plan.tasks:
        logger.debug(
            "investment_document_review.todo_plan.task session_id=%s task_id=%s "
            "task_kind=%s title=%s depends_on=%s completion_criteria_count=%s",
            session_id,
            task.id,
            task.kind.value,
            task.title,
            ",".join(task.depends_on) if task.depends_on else "",
            len(task.completion_criteria),
        )


def _build_chunk_review_analyze_tasks(
    *,
    analyze_focus: list[str],
    extract_task_ids: list[str],
) -> list[dict[str, Any]]:
    normalized_counts: dict[str, int] = {}
    analyze_tasks: list[dict[str, Any]] = []

    for focus in analyze_focus:
        if not isinstance(focus, str):
            continue
        cleaned_focus = focus.strip()
        if not cleaned_focus:
            continue

        normalized_focus = _normalize_todo_task_id_fragment(cleaned_focus)
        occurrence = normalized_counts.get(normalized_focus, 0) + 1
        normalized_counts[normalized_focus] = occurrence
        task_id = f"{ANALYZE_TASK_ID_PREFIX}_{normalized_focus}"
        if occurrence > 1:
            task_id = f"{task_id}_{occurrence}"

        analyze_tasks.append(
            {
                "id": task_id,
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "title": f"Analyze {cleaned_focus}",
                "description": (
                    "Review the extracted chunk evidence for this dimension and "
                    "identify supported risks, inconsistencies, limits, and gaps."
                ),
                "payload": {ANALYZE_FOCUS_FIELD: [cleaned_focus]},
                "depends_on": extract_task_ids,
                "completion_criteria": [
                    f"Findings stay focused on {cleaned_focus}.",
                    "Findings are based only on successful chunk extraction results.",
                    "Material gaps, conflicts, and boundary limits are identified.",
                ],
            }
        )

    if analyze_tasks:
        return analyze_tasks

    return [
        {
            "id": AGGREGATE_ANALYZE_TASK_ID,
            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
            "title": "Analyze aggregated chunk evidence",
            "description": (
                "Merge evidence extracted from every document chunk and analyze "
                "risks, disclosure quality, inconsistencies, constraints, and gaps."
            ),
            "payload": {ANALYZE_FOCUS_FIELD: []},
            "depends_on": extract_task_ids,
            "completion_criteria": [
                "Findings are based only on successful chunk extraction results.",
                "Cross-chunk conflicts, limitations, and disclosure gaps are identified.",
            ],
        }
    ]


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
    todo_plan: TodoExecutionPlan,
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


def build_review_todo_plan_payload(
    state: InvestmentDocumentReviewState,
) -> dict[str, Any]:
    if state.review_payload is None:
        raise RuntimeError("Document review flow has no review payload to plan.")

    return {
        DOCUMENT_TEXT_FIELD: state.review_payload.get(DOCUMENT_TEXT_FIELD),
        "document_type": state.review_payload.get("document_type"),
        EXTRACT_FOCUS_FIELD: state.review_payload.get(EXTRACT_FOCUS_FIELD),
        ANALYZE_FOCUS_FIELD: state.review_payload.get(ANALYZE_FOCUS_FIELD),
        REVIEW_GOAL_FIELD: state.review_payload.get(REVIEW_GOAL_FIELD),
    }


def _build_review_todo_common_payload(
    *,
    state: InvestmentDocumentReviewState,
    task,
) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "task_title": task.title,
        "task_description": task.description,
        "completion_criteria": task.completion_criteria,
        "document_type": state.document_type,
        REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
    }


def _build_review_todo_extract_payload(
    *,
    state: InvestmentDocumentReviewState,
    task,
) -> dict[str, Any]:
    return InvestmentDocumentReviewExtractInput.model_validate(
        {
            **_build_review_todo_common_payload(state=state, task=task),
            DOCUMENT_TEXT_FIELD: task.payload.get(
                DOCUMENT_TEXT_FIELD,
                state.input_payload.get(DOCUMENT_TEXT_FIELD),
            ),
            EXTRACT_FOCUS_FIELD: task.payload.get(EXTRACT_FOCUS_FIELD, []),
            CHUNK_INDEX_FIELD: task.payload.get(CHUNK_INDEX_FIELD),
            CHUNK_COUNT_FIELD: task.payload.get(CHUNK_COUNT_FIELD),
            CHUNK_REVIEW_SCOPE_FIELD: task.payload.get(
                CHUNK_REVIEW_SCOPE_FIELD,
                FULL_DOCUMENT_REVIEW_SCOPE,
            ),
        }
    ).model_dump(exclude_none=True, exclude_defaults=True)


def _build_review_todo_analyze_payload(
    *,
    state: InvestmentDocumentReviewState,
    task,
    dependency_results: list[TodoTaskResult],
) -> dict[str, Any]:
    return InvestmentDocumentReviewAnalyzeInput.model_validate(
        {
            **_build_review_todo_common_payload(state=state, task=task),
            DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
            ANALYZE_FOCUS_FIELD: task.payload.get(ANALYZE_FOCUS_FIELD, []),
            "dependency_results": [result.model_dump() for result in dependency_results],
        }
    ).model_dump()


def _build_review_todo_dependency_results(
    *,
    task,
    executed_results_by_id: dict[str, TodoTaskResult],
) -> list[TodoTaskResult]:
    if not task.depends_on:
        raise RuntimeError(
            "Analyze To-Do tasks must depend on at least one upstream task result."
        )

    dependency_results: list[TodoTaskResult] = []
    missing_dependency_ids: list[str] = []
    failed_dependency_ids: list[str] = []

    for dependency_task_id in task.depends_on:
        dependency_result = executed_results_by_id.get(dependency_task_id)
        if dependency_result is None:
            missing_dependency_ids.append(dependency_task_id)
            continue
        if dependency_result.status != TodoTaskStatus.SUCCEEDED:
            failed_dependency_ids.append(dependency_task_id)
            continue
        dependency_results.append(dependency_result)

    if missing_dependency_ids:
        raise RuntimeError(
            "Analyze To-Do task is missing required dependency results: "
            + ", ".join(missing_dependency_ids)
        )

    if failed_dependency_ids:
        raise RuntimeError(
            "Analyze To-Do task has non-succeeded dependency results: "
            + ", ".join(failed_dependency_ids)
        )

    return dependency_results


def _build_review_todo_synthesize_payload(
    *,
    state: InvestmentDocumentReviewState,
    executed_results_by_id: dict[str, TodoTaskResult],
) -> dict[str, Any]:
    if state.todo_plan is None:
        raise RuntimeError("Document review flow has no To-Do plan to synthesize.")

    completed_results = _build_completed_todo_results(
        state.todo_plan,
        executed_results_by_id,
    )
    return InvestmentDocumentReviewSynthesizeInput.model_validate(
        {
            "document_type": state.document_type,
            ROUTE_REASON_FIELD: state.route_reason or "",
            ROUTE_CONFIDENCE_FIELD: state.route_confidence or 0.0,
            REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
            "todo_plan": state.todo_plan.model_dump(),
            "todo_results": [result.model_dump() for result in completed_results],
            "review_summary": _build_review_todo_summary(
                todo_plan=state.todo_plan,
                completed_results=completed_results,
            ).model_dump(),
        }
    ).model_dump()


def _build_known_type_full_document_plan(
    state: InvestmentDocumentReviewState,
) -> TodoExecutionPlan:
    if state.review_framework is None:
        raise RuntimeError("Known document type must have review framework")
    if state.review_payload is None:
        raise RuntimeError("Document review flow has no review payload")

    extract_focus = state.review_framework.extract_focus
    analyze_focus = state.review_framework.analyze_focus

    extract_task = {
        "id": FULL_DOCUMENT_EXTRACT_TASK_ID,
        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
        "title": "Extract evidence from full document",
        "description": (
            "Extract key facts, fees, risks, constraints, disclosures, gaps, "
            "and source citations from the complete document."
        ),
        "payload": {
            DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
            EXTRACT_FOCUS_FIELD: extract_focus,
            CHUNK_REVIEW_SCOPE_FIELD: FULL_DOCUMENT_REVIEW_SCOPE,
        },
        "depends_on": [],
        "completion_criteria": [
            "Output contains only facts and evidence from the document.",
            "Important gaps are recorded as information gaps.",
            "Source citations identify supporting sections.",
        ],
    }

    analyze_tasks = _build_chunk_review_analyze_tasks(
        analyze_focus=analyze_focus,
        extract_task_ids=[FULL_DOCUMENT_EXTRACT_TASK_ID],
    )
    for task in analyze_tasks:
        task["completion_criteria"] = [
            f"Findings stay focused on {task['payload'][ANALYZE_FOCUS_FIELD][0]}.",
            "Findings are based only on successful extraction results.",
            "Material gaps, conflicts, and boundary limits are identified.",
        ]

    analyze_task_ids = [task["id"] for task in analyze_tasks]

    synthesize_task = {
        "id": SYNTHESIZE_REVIEW_TASK_ID,
        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
        "title": "Synthesize full-document review",
        "description": (
            "Produce the final investment document review from the extracted "
            "evidence and analysis results."
        ),
        "payload": {},
        "depends_on": analyze_task_ids,
        "completion_criteria": [
            "Final review covers all extracted evidence.",
            "Facts, risks, gaps, boundary notes, and summary are supported.",
        ],
    }

    tasks = [extract_task] + analyze_tasks + [synthesize_task]
    document_type_label = state.document_type.value if state.document_type else "document"
    todo_plan = TodoExecutionPlan.model_validate({
        "tasks": tasks,
        "summary": (
            f"Extract evidence from the {document_type_label}, "
            f"analyze by review dimension, and synthesize the final review."
        ),
    })

    ensure_valid_todo_plan(todo_plan)
    return todo_plan


def _build_chunk_review_todo_plan(
    state: InvestmentDocumentReviewState,
) -> TodoExecutionPlan:
    if state.review_payload is None:
        raise RuntimeError("Document review flow has no review payload for chunk review.")

    chunk_count = len(state.document_chunks)
    extract_task_ids = [
        f"{CHUNK_EXTRACT_TASK_ID_PREFIX}_{idx + 1:04d}"
        for idx in range(chunk_count)
    ]
    extract_focus = state.review_payload.get(EXTRACT_FOCUS_FIELD) or []
    analyze_focus = state.review_payload.get(ANALYZE_FOCUS_FIELD) or []
    analyze_tasks = _build_chunk_review_analyze_tasks(
        analyze_focus=analyze_focus,
        extract_task_ids=extract_task_ids,
    )
    analyze_task_ids = [task["id"] for task in analyze_tasks]
    tasks = [
        {
            "id": task_id,
            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
            "title": f"Extract evidence from document chunk {idx + 1} of {chunk_count}",
            "description": (
                "Extract lightweight, document-grounded evidence from this chunk: "
                "key facts, fees, risks, constraints, disclosures, gaps, unusual "
                "statements, and source citations."
            ),
            "payload": {
                DOCUMENT_TEXT_FIELD: chunk,
                EXTRACT_FOCUS_FIELD: extract_focus,
                CHUNK_INDEX_FIELD: idx,
                CHUNK_COUNT_FIELD: chunk_count,
                CHUNK_REVIEW_SCOPE_FIELD: CHUNK_REVIEW_SCOPE,
            },
            "depends_on": [],
            "completion_criteria": [
                "Output contains only facts and evidence visible in this chunk.",
                "Important missing or weak evidence is recorded as information gaps.",
                "Source citations identify the supporting chunk text or section.",
            ],
        }
        for idx, (task_id, chunk) in enumerate(
            zip(extract_task_ids, state.document_chunks, strict=True)
        )
    ]
    tasks.extend(
        analyze_tasks
        + [
            {
                "id": SYNTHESIZE_REVIEW_TASK_ID,
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                "title": "Synthesize full-document review",
                "description": (
                    "Produce the final investment document review from the aggregated "
                    "chunk evidence and analysis results."
                ),
                "payload": {},
                "depends_on": analyze_task_ids,
                "completion_criteria": [
                    "Final review covers extracted evidence from all document chunks.",
                    "Facts, risks, gaps, boundary notes, and summary are supported by task results.",
                ],
            },
        ]
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": tasks,
            "summary": (
                "Extract lightweight evidence from every document chunk, analyze the "
                "evidence by review dimension, then synthesize the full document review."
            ),
        }
    )
    ensure_valid_todo_plan(todo_plan)
    return todo_plan


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
            _build_review_todo_extract_payload(state=state, task=task),
        )

    if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE:
        return (
            INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
            _build_review_todo_synthesize_payload(
                state=state,
                executed_results_by_id=executed_results_by_id,
            ),
        )

    if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE:
        return (
            INVESTMENT_DOCUMENT_ANALYZE_TASK,
            _build_review_todo_analyze_payload(
                state=state,
                task=task,
                dependency_results=_build_review_todo_dependency_results(
                    task=task,
                    executed_results_by_id=executed_results_by_id,
                ),
            ),
        )

    raise RuntimeError(f"Unsupported investment document To-Do task kind: {task.kind.value}")


def generate_review_todo_plan(
    state: InvestmentDocumentReviewState,
    executor: TaskExecutor,
) -> dict[str, Any]:
    if should_use_code_built_plan(state):
        try:
            if is_chunked_document(state):
                todo_plan = _build_chunk_review_todo_plan(state)
            else:
                todo_plan = _build_known_type_full_document_plan(state)
        except (ValidationError, TodoPlanValidationException) as exc:
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                    error=normalize_task_error(exc, stage="output_validation"),
                )
            }

        _log_review_todo_plan_generated(
            session_id=state.session_id,
            todo_plan=todo_plan,
            document_type=state.document_type,
            chunk_count=len(state.document_chunks) if is_chunked_document(state) else 0,
        )
        return {"todo_plan": todo_plan}

    plan_payload = build_review_todo_plan_payload(state)
    result = executor.run(
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
        plan_payload,
    )
    if not result.ok:
        return {"output": result}

    try:
        todo_plan = TodoExecutionPlan.model_validate(result.result)
        ensure_valid_todo_plan(todo_plan)
    except (ValidationError, TodoPlanValidationException) as exc:
        return {
            "output": TaskResult(
                ok=False,
                task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                error=normalize_task_error(exc, stage="output_validation"),
            )
        }

    _log_review_todo_plan_generated(
        session_id=state.session_id,
        todo_plan=todo_plan,
        document_type=state.document_type,
        chunk_count=len(state.document_chunks) if is_chunked_document(state) else 0,
    )
    return {"todo_plan": todo_plan}


def execute_review_todo_plan(
    state: InvestmentDocumentReviewState,
    executor: TaskExecutor,
    todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None,
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
    runner = _build_todo_execution_runner(
        state,
        executor,
        resume_state=resume_state,
    )
    todo_results = asyncio.run(
        runner.run(state.todo_plan, resume_state=resume_state)
    )
    synthesize_result = _find_succeeded_todo_result(
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
        update["output"] = TaskResult(
            ok=False,
            task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            error=normalize_task_error(
                RuntimeError("Chunk-based document review did not produce synthesis."),
                stage="output_validation",
            ),
        )
    return update
