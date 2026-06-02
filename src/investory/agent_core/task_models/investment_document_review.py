from pydantic import BaseModel, Field

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)


class InvestmentDocumentReviewInput(BaseModel):
    document_text: str = Field(
        description="Full text of the investment-related document to review."
    )
    document_type: InvestmentDocumentType = Field(
        description="Classified document type used to select the review framework."
    )
    extract_focus: list[str] = Field(
        description="Facts or sections the review should extract from the document."
    )
    analyze_focus: list[str] = Field(
        description="Risk or quality angles the review should analyze."
    )
    review_goal: str | None = Field(
        default=None,
        description="Optional user goal that narrows the review focus without changing policy boundaries.",
    )


class InvestmentDocumentReviewResult(BaseModel):
    document_type: InvestmentDocumentType = Field(
        description="Reviewed document type used for the single-pass analysis."
    )
    extracted_facts: list[str] = Field(
        description="Key facts explicitly grounded in the provided document."
    )
    risk_findings: list[str] = Field(
        description="Risks, caveats, or issues found in the document."
    )
    information_gaps: list[str] = Field(
        description="Missing information that prevents a more complete review."
    )
    boundary_notes: list[str] = Field(
        description="Notes that clarify source limits and non-advisory boundaries."
    )
    summary: str = Field(
        description="Concise overall review summary grounded in the document."
    )
    learning_next_steps: list[str] | None = Field(
        default=None,
        description="Optional educational follow-up directions that stay within learning boundaries.",
    )
