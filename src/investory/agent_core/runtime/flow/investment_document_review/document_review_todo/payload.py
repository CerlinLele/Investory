"""Todo task payload builders for extract, analyze, and synthesize tasks."""

from typing import Any

from investory.agent_core.contracts.investment_document_review_state import (
    ANALYZE_FOCUS_FIELD,
    DOCUMENT_TEXT_FIELD,
    EXTRACT_FOCUS_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewState,
)
from investory.agent_core.contracts.todo_execution import (
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    CHUNK_COUNT_FIELD,
    CHUNK_INDEX_FIELD,
    CHUNK_REVIEW_SCOPE_FIELD,
    FULL_DOCUMENT_REVIEW_SCOPE,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeInput,
    InvestmentDocumentReviewExtractInput,
    InvestmentDocumentReviewSynthesizeInput,
)

from .summary import (
    build_completed_todo_results,
    build_review_todo_summary,
)


def build_review_todo_common_payload(
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


def build_review_todo_extract_payload(
    *,
    state: InvestmentDocumentReviewState,
    task,
) -> dict[str, Any]:
    return InvestmentDocumentReviewExtractInput.model_validate(
        {
            **build_review_todo_common_payload(state=state, task=task),
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


def build_review_todo_analyze_payload(
    *,
    state: InvestmentDocumentReviewState,
    task,
    dependency_results: list[TodoTaskResult],
) -> dict[str, Any]:
    return InvestmentDocumentReviewAnalyzeInput.model_validate(
        {
            **build_review_todo_common_payload(state=state, task=task),
            DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
            ANALYZE_FOCUS_FIELD: task.payload.get(ANALYZE_FOCUS_FIELD, []),
            "dependency_results": [result.model_dump() for result in dependency_results],
        }
    ).model_dump()


def build_review_todo_dependency_results(
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


def build_review_todo_synthesize_payload(
    *,
    state: InvestmentDocumentReviewState,
    executed_results_by_id: dict[str, TodoTaskResult],
) -> dict[str, Any]:
    if state.todo_plan is None:
        raise RuntimeError("Document review flow has no To-Do plan to synthesize.")

    completed_results = build_completed_todo_results(
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
            "review_summary": build_review_todo_summary(
                todo_plan=state.todo_plan,
                completed_results=completed_results,
            ).model_dump(),
        }
    ).model_dump()