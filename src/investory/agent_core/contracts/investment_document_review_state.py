from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.todo_execution import TodoExecutionPlan


DOCUMENT_TEXT_FIELD = "document_text"
DOCUMENT_TYPE_HINT_FIELD = "document_type_hint"
REVIEW_GOAL_FIELD = "review_goal"


class InvestmentDocumentType(str, Enum):
    ETF_FACTSHEET = "etf_factsheet"
    FUND_PROSPECTUS = "fund_prospectus"
    PRODUCT_BROCHURE = "product_brochure"
    EARNINGS_REPORT = "earnings_report"
    LEARNING_MATERIAL = "learning_material"
    UNKNOWN = "unknown"


class InvestmentDocumentReviewRouteDecision(BaseModel):
    document_type: InvestmentDocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


class DocumentReviewFramework(BaseModel):
    extract_focus: list[str] = Field(default_factory=list)
    analyze_focus: list[str] = Field(default_factory=list)


class InvestmentDocumentReviewState(BaseModel):
    session_id: str | None = None
    input_payload: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list)
    document_type: InvestmentDocumentType | None = None
    route_reason: str | None = None
    route_confidence: float | None = None
    review_framework: DocumentReviewFramework | None = None
    review_payload: dict[str, Any] | None = None
    todo_plan: TodoExecutionPlan | None = None
    output: TaskResult | None = None


__all__ = [
    "DOCUMENT_TEXT_FIELD",
    "DOCUMENT_TYPE_HINT_FIELD",
    "REVIEW_GOAL_FIELD",
    "DocumentReviewFramework",
    "InvestmentDocumentReviewRouteDecision",
    "InvestmentDocumentReviewState",
    "InvestmentDocumentType",
]
