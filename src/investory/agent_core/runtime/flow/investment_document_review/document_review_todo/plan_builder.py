"""Todo plan generation strategies: code-built and LLM-based."""

import logging
import re
from typing import Any

from pydantic import ValidationError

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
    TodoTaskKind,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    AGGREGATE_ANALYZE_TASK_ID,
    ANALYZE_TASK_ID_PREFIX,
    CHUNK_EXTRACT_TASK_ID_PREFIX,
    CHUNK_REVIEW_SCOPE,
    CHUNK_REVIEW_SCOPE_FIELD,
    FULL_DOCUMENT_EXTRACT_TASK_ID,
    FULL_DOCUMENT_REVIEW_SCOPE,
    SYNTHESIZE_REVIEW_TASK_ID,
    CHUNK_COUNT_FIELD,
    CHUNK_INDEX_FIELD,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.runtime.todo_core.plan_validator import (
    TodoPlanValidationException,
    ensure_valid_todo_plan,
)
from investory.agent_core.tasks import INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK

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