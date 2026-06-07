from pydantic import BaseModel, Field

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewResult,
)


class InvestmentDocumentReviewTodoTaskInput(BaseModel):
    task_id: str = Field(description="Stable To-Do task id from the review plan.")
    task_title: str = Field(description="Human-readable To-Do task title.")
    task_description: str = Field(description="Specific task instruction to execute.")
    completion_criteria: list[str] = Field(
        description="Criteria the task output must satisfy."
    )
    document_type: InvestmentDocumentType = Field(
        description="Classified document type selected by the review router."
    )
    review_goal: str | None = Field(
        default=None,
        description="Optional user goal that narrows the review focus without changing policy boundaries.",
    )


class InvestmentDocumentReviewExtractInput(InvestmentDocumentReviewTodoTaskInput):
    document_text: str = Field(
        description="Full text of the investment-related document to extract from."
    )
    extract_focus: list[str] = Field(
        description="Facts or sections this extract task should capture."
    )


class InvestmentDocumentReviewExtractResult(BaseModel):
    extracted_facts: list[str] = Field(
        description="Facts explicitly grounded in the provided document."
    )
    source_citations: list[str] = Field(
        description="Document snippets or section references supporting the extracted facts."
    )
    information_gaps: list[str] = Field(
        description="Missing source details that limited extraction."
    )
    boundary_notes: list[str] = Field(
        description="Source-limit notes that avoid analysis or investment advice."
    )
    summary: str = Field(description="Brief factual extraction summary.")


class InvestmentDocumentReviewAnalyzeInput(InvestmentDocumentReviewTodoTaskInput):
    document_text: str = Field(
        description="Full text of the investment-related document for grounding checks."
    )
    analyze_focus: list[str] = Field(
        description="Risk, quality, or consistency angles this analyze task should assess."
    )
    dependency_results: list[TodoTaskResult] = Field(
        description="Completed upstream extract task results required for analysis."
    )


class InvestmentDocumentReviewAnalyzeResult(BaseModel):
    risk_findings: list[str] = Field(
        description="Risks, caveats, or consistency issues supported by upstream facts."
    )
    supporting_evidence: list[str] = Field(
        description="Fact references or snippets that support the findings."
    )
    information_gaps: list[str] = Field(
        description="Missing information that limits the analysis."
    )
    boundary_notes: list[str] = Field(
        description="Non-advisory and source-limit notes for the analysis."
    )
    summary: str = Field(description="Brief analysis summary.")


class InvestmentDocumentReviewTodoTaskSummary(BaseModel):
    task_id: str = Field(description="Stable To-Do task id.")
    task_title: str | None = Field(
        default=None,
        description="Human-readable task title from the To-Do plan, when available.",
    )
    task_kind: TodoTaskKind | None = Field(
        default=None,
        description="Task kind from the To-Do plan, when available.",
    )
    status: TodoTaskStatus = Field(description="Completed task result status.")
    summary: str | None = Field(
        default=None,
        description="Brief task-level summary extracted from the task result or error.",
    )


class InvestmentDocumentReviewTodoSummary(BaseModel):
    plan_summary: str = Field(description="Summary from the validated To-Do plan.")
    planned_task_count: int = Field(
        ge=0,
        description="Number of tasks in the validated To-Do plan.",
    )
    completed_task_count: int = Field(
        ge=0,
        description="Number of completed task results available for synthesis.",
    )
    succeeded_task_ids: list[str] = Field(
        description="Completed task ids with succeeded status."
    )
    failed_task_ids: list[str] = Field(
        description="Completed task ids with failed status."
    )
    skipped_task_ids: list[str] = Field(
        description="Completed task ids with skipped status."
    )
    extracted_facts: list[str] = Field(
        description="Fact lists consolidated from successful task results."
    )
    risk_findings: list[str] = Field(
        description="Risk finding lists consolidated from successful task results."
    )
    information_gaps: list[str] = Field(
        description="Information gap lists consolidated from successful task results."
    )
    boundary_notes: list[str] = Field(
        description="Boundary note lists consolidated from successful task results."
    )
    task_summaries: list[InvestmentDocumentReviewTodoTaskSummary] = Field(
        description="Ordered per-task completion summaries for synthesis."
    )


class InvestmentDocumentReviewSynthesizeInput(BaseModel):
    document_type: InvestmentDocumentType = Field(
        description="Classified document type used for the final review."
    )
    route_reason: str = Field(description="Reason produced by document type routing.")
    route_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Router confidence for the selected document type.",
    )
    review_goal: str | None = Field(
        default=None,
        description="Optional user goal that narrowed the review focus.",
    )
    todo_plan: TodoExecutionPlan = Field(
        description="Validated To-Do plan used for the review."
    )
    todo_results: list[TodoTaskResult] = Field(
        description="Ordered results produced by executing the To-Do plan."
    )
    review_summary: InvestmentDocumentReviewTodoSummary = Field(
        description="Deterministic aggregation of the plan and completed task results."
    )


InvestmentDocumentReviewSynthesizeResult = InvestmentDocumentReviewResult


__all__ = [
    "InvestmentDocumentReviewAnalyzeInput",
    "InvestmentDocumentReviewAnalyzeResult",
    "InvestmentDocumentReviewExtractInput",
    "InvestmentDocumentReviewExtractResult",
    "InvestmentDocumentReviewSynthesizeInput",
    "InvestmentDocumentReviewSynthesizeResult",
    "InvestmentDocumentReviewTodoTaskInput",
    "InvestmentDocumentReviewTodoTaskSummary",
    "InvestmentDocumentReviewTodoSummary",
]
