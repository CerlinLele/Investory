from enum import Enum

from pydantic import BaseModel, Field, model_validator

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


INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME = "investment_document_risk_assessment"
COMPLIANCE_REVIEWER_ROLE = "compliance_reviewer"


class InvestmentDocumentReviewRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InvestmentDocumentReviewApprovalStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    HUMAN_APPROVED = "human_approved"
    CANCELLED = "cancelled"


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


class InvestmentDocumentReviewRiskAssessmentInput(BaseModel):
    document_type: InvestmentDocumentType = Field(
        description="Reviewed document type used to contextualize the risk assessment."
    )
    route_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Router confidence for the selected document type.",
    )
    risk_findings: list[str] = Field(
        description="Structured risk findings aggregated from prior review steps."
    )
    information_gaps: list[str] = Field(
        description="Missing details that reduce confidence in the review outcome."
    )
    boundary_notes: list[str] = Field(
        description="Boundary and scope notes carried forward from the review."
    )
    task_status_summary: list[str] = Field(
        description="Execution-status summaries from prior review tasks."
    )


class InvestmentDocumentReviewRiskAssessmentResult(BaseModel):
    overall_risk: InvestmentDocumentReviewRiskLevel = Field(
        description="Machine-readable overall risk level for the completed review."
    )
    risk_reason: str = Field(
        description="Short explanation of the overall risk classification."
    )
    critical_issues: list[str] = Field(
        description="Critical issues that block automatic downstream release."
    )
    approval_status: InvestmentDocumentReviewApprovalStatus = Field(
        description="Machine-readable approval state derived from the risk level."
    )
    required_role: str | None = Field(
        default=None,
        description="Role required for manual approval when automatic release is blocked.",
    )
    auto_proceed: bool = Field(
        description="Whether downstream systems may proceed without human approval."
    )

    @model_validator(mode="after")
    def _fix_risk_consistency(self) -> "InvestmentDocumentReviewRiskAssessmentResult":
        # Rule 1: critical_issues non-empty ⟹ approval_status must be PENDING_HUMAN_APPROVAL
        if self.critical_issues and self.approval_status == InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED:
            self.approval_status = InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL

        # Rule 2: approval_status == PENDING_HUMAN_APPROVAL ⟹ auto_proceed must be False
        if self.approval_status == InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL and self.auto_proceed:
            self.auto_proceed = False

        # Rule 3: overall_risk == HIGH ⟹ critical_issues must be non-empty
        if self.overall_risk == InvestmentDocumentReviewRiskLevel.HIGH and not self.critical_issues:
            self.critical_issues = ["Risk level is HIGH; requires human review due to unspecified critical concerns"]

        # Rule 4: approval_status == PENDING_HUMAN_APPROVAL ⟹ critical_issues must be non-empty
        if self.approval_status == InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL and not self.critical_issues:
            self.critical_issues = ["Approval is pending human review; auto-generated for consistency"]

        return self
