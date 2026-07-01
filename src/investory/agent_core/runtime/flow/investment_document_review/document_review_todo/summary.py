"""Todo results aggregation and summary building."""

from typing import Any

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    COMPLETED_TODO_RESULT_STATUSES,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewTodoSummary,
    InvestmentDocumentReviewTodoTaskSummary,
)


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


def build_completed_todo_results(
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


def find_succeeded_todo_result(
    todo_results: list[TodoTaskResult],
    task_id: str,
) -> TodoTaskResult | None:
    for result in todo_results:
        if result.id == task_id and result.status == TodoTaskStatus.SUCCEEDED:
            return result
    return None


def build_review_todo_summary(
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


def build_review_task_status_summary(
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