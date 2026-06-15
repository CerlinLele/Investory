from pydantic import BaseModel, Field

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoTaskResult,
)
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewResult,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewTodoSummary,
)


class InvestmentDocumentReviewReflectionInput(BaseModel):
    document_type: InvestmentDocumentType = Field(
        description="Classified document type for the review being checked."
    )
    route_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Router confidence for the selected document type.",
    )
    review_goal: str | None = Field(
        default=None,
        description="Optional user goal that narrowed the review focus.",
    )
    review_result: InvestmentDocumentReviewResult = Field(
        description="Current structured review result to evaluate and optionally revise."
    )
    todo_plan: TodoExecutionPlan | None = Field(
        default=None,
        description="Validated To-Do plan used for long document review, when available.",
    )
    todo_results: list[TodoTaskResult] = Field(
        default_factory=list,
        description="Ordered To-Do execution results supporting the review.",
    )
    review_summary: InvestmentDocumentReviewTodoSummary | None = Field(
        default=None,
        description="Deterministic aggregation of To-Do results, when available.",
    )
    criteria: list[str] = Field(
        description="Explicit review-quality criteria used for reflection."
    )
    max_rounds: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Maximum revision rounds allowed by the reflection task.",
    )


class InvestmentDocumentReviewReflectionCritique(BaseModel):
    passed: bool = Field(description="Whether the review result satisfies the criteria.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality score for the current or revised review result.",
    )
    issues: list[str] = Field(description="Criteria failures or quality issues found.")
    suggestions: list[str] = Field(
        description="Concrete improvements applied or recommended."
    )
    safety_flags: list[str] = Field(
        default_factory=list,
        description="Safety or boundary risks found during reflection.",
    )


class InvestmentDocumentReviewReflectionResult(BaseModel):
    review_result: InvestmentDocumentReviewResult = Field(
        description="Structured review result after reflection."
    )
    passed: bool = Field(description="Whether the reflected review satisfies criteria.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality score for the reflected review result.",
    )
    issues: list[str] = Field(description="Criteria failures or quality issues found.")
    suggestions: list[str] = Field(
        description="Concrete improvements applied or recommended."
    )
    safety_flags: list[str] = Field(
        default_factory=list,
        description="Safety or boundary risks found during reflection.",
    )
    rounds: int = Field(
        ge=0,
        le=2,
        description="Number of revision rounds used.",
    )


__all__ = [
    "InvestmentDocumentReviewReflectionCritique",
    "InvestmentDocumentReviewReflectionInput",
    "InvestmentDocumentReviewReflectionResult",
]
