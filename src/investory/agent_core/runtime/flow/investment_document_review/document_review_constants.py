from enum import Enum
from typing import TYPE_CHECKING, Protocol

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoTaskStatus,
)

if TYPE_CHECKING:
    pass


# Task name
INVESTMENT_DOCUMENT_REVIEW_TASK_NAME = "investment_document_review"

# Field constants
ACTION_FIELD = "action"
MESSAGE_FIELD = "message"
DOCUMENT_TYPE_FIELD = "document_type"
REVIEW_FIELD = "review"
RISK_ASSESSMENT_FIELD = "risk_assessment"
APPROVAL_FIELD = "approval"
STATUS_FIELD = "status"
REQUIRED_ROLE_FIELD = "required_role"
MISSING_FIELDS_FIELD = "missing_fields"
ROUTE_REASON_FIELD = "route_reason"
ROUTE_CONFIDENCE_FIELD = "route_confidence"
REVIEW_RESULT_FIELD = "review_result"
TODO_PLAN_FIELD = "todo_plan"
TODO_RESULTS_FIELD = "todo_results"
REVIEW_SUMMARY_FIELD = "review_summary"
CRITERIA_FIELD = "criteria"
MAX_ROUNDS_FIELD = "max_rounds"
DEFAULT_REFLECTION_MAX_ROUNDS = 1

# Route constants
MISSING_ROUTE = "missing"
REFUSAL_ROUTE = "refusal"
COMPLETE_ROUTE = "complete"
PENDING_APPROVAL_ROUTE = "pending_approval"

# Chunk / review scope constants
CHUNK_INDEX_FIELD = "chunk_index"
CHUNK_COUNT_FIELD = "chunk_count"
CHUNK_REVIEW_SCOPE_FIELD = "review_scope"
FULL_DOCUMENT_REVIEW_SCOPE = "full_document"
CHUNK_REVIEW_SCOPE = "document_chunk"
CHUNK_EXTRACT_TASK_ID_PREFIX = "extract_chunk"
FULL_DOCUMENT_EXTRACT_TASK_ID = "extract_full_document"
ANALYZE_TASK_ID_PREFIX = "analyze"
AGGREGATE_ANALYZE_TASK_ID = "analyze_aggregated_chunk_evidence"
SYNTHESIZE_REVIEW_TASK_ID = "synthesize_full_document_review"
COMPLETED_TODO_RESULT_STATUSES = {
    TodoTaskStatus.SUCCEEDED,
    TodoTaskStatus.FAILED,
    TodoTaskStatus.SKIPPED,
}

# Message constants
MISSING_INPUT_MESSAGE = (
    "Please provide the missing document material or a clearer document type hint "
    "so the review can continue."
)
CLASSIFICATION_CLARIFICATION_MESSAGE = (
    "Please clarify the document type or provide more review context so the "
    "document review can continue."
)
REFUSAL_MESSAGE = (
    "This flow cannot handle buy, sell, hold, timing, allocation, or real-time "
    "market requests. It can only review the provided document for facts, risks, "
    "and information gaps."
)

# Reflection criteria
INVESTMENT_DOCUMENT_REVIEW_REFLECTION_CRITERIA = [
    (
        "Review results must be based only on the input document, To-Do plan, "
        "To-Do results, and deterministic review summary."
    ),
    (
        "Extracted facts must come from successful extract, analyze, or "
        "synthesize results."
    ),
    (
        "Risk findings must be supported by evidence and must not provide buy, "
        "sell, hold, timing, allocation, or return-prediction advice."
    ),
    (
        "Failed or skipped tasks must be reflected in information_gaps or "
        "boundary_notes."
    ),
    (
        "The summary should be concise, audit-friendly, and clear about key "
        "risks and limitations."
    ),
    "The output must preserve the InvestmentDocumentReviewResult structure.",
]


class InvestmentDocumentReviewAction(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    COMPLETE = "complete"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"


class InvestmentDocumentReviewNode(str, Enum):
    EVALUATE_POLICY_GATE = "evaluate_policy_gate"
    CLASSIFY_DOCUMENT_TYPE = "classify_document_type"
    BUILD_REVIEW_FRAMEWORK = "build_review_framework"
    GENERATE_REVIEW_TODO_PLAN = "generate_review_todo_plan"
    EXECUTE_REVIEW_TODO_PLAN = "execute_review_todo_plan"
    RUN_SINGLE_PASS_REVIEW = "run_single_pass_review"
    REFLECT_REVIEW_OUTPUT = "reflect_review_output"
    ASSESS_REVIEW_RISK = "assess_review_risk"
    BUILD_FINAL_RESULT = "build_final_result"
    BUILD_PENDING_APPROVAL_RESULT = "build_pending_approval_result"
    BUILD_MISSING_INPUT_RESULT = "build_missing_input_result"
    BUILD_REFUSAL_RESULT = "build_refusal_result"


class InvestmentDocumentReviewTodoResumeStore(Protocol):
    # This checkpoint persists only review-task execution. Future approval resume
    # metadata stays on InvestmentDocumentReviewState and should not rerun review work.
    def load_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
    ) -> TodoExecutionResumeState | None: ...

    def save_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
        results: list,
        previous_resume_state: TodoExecutionResumeState | None,
    ) -> None: ...
