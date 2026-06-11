from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.runtime.message_builder import build_prompt_messages
from investory.agent_core.task_models.investment_document_review import (
    COMPLIANCE_REVIEWER_ROLE,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    InvestmentDocumentReviewApprovalStatus,
    InvestmentDocumentReviewInput,
    InvestmentDocumentReviewRiskAssessmentInput,
    InvestmentDocumentReviewRiskAssessmentResult,
    InvestmentDocumentReviewRiskLevel,
    InvestmentDocumentReviewResult,
)


def test_investment_document_review_input_accepts_expected_payload() -> None:
    payload = InvestmentDocumentReviewInput.model_validate(
        {
            "document_text": "ETF factsheet covering fees and tracking index.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["fees", "index"],
            "analyze_focus": ["risk disclosures"],
            "review_goal": "Check fees and risks",
        }
    )

    assert payload.document_type is InvestmentDocumentType.ETF_FACTSHEET
    assert payload.review_goal == "Check fees and risks"


def test_investment_document_review_result_allows_optional_learning_steps() -> None:
    result = InvestmentDocumentReviewResult.model_validate(
        {
            "document_type": InvestmentDocumentType.FUND_PROSPECTUS,
            "extracted_facts": ["The fund may suspend redemptions in rare cases."],
            "risk_findings": ["Liquidity risk is disclosed."],
            "information_gaps": ["No fee example is provided."],
            "boundary_notes": ["The review does not assess current market conditions."],
            "summary": "The prospectus outlines constraints and risks but leaves fee examples unclear.",
        }
    )

    assert result.learning_next_steps is None


def test_investment_document_review_risk_assessment_constants_are_stable() -> None:
    assert INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME == (
        "investment_document_risk_assessment"
    )
    assert COMPLIANCE_REVIEWER_ROLE == "compliance_reviewer"


def test_investment_document_review_risk_assessment_input_accepts_expected_payload() -> None:
    payload = InvestmentDocumentReviewRiskAssessmentInput.model_validate(
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_confidence": 0.92,
            "risk_findings": ["Fee disclosure is incomplete."],
            "information_gaps": ["No benchmark methodology is provided."],
            "boundary_notes": ["The review does not assess live market conditions."],
            "task_status_summary": ["analyze-fees: succeeded", "analyze-risk: skipped"],
        }
    )

    assert payload.document_type is InvestmentDocumentType.ETF_FACTSHEET
    assert payload.route_confidence == 0.92
    assert payload.task_status_summary == [
        "analyze-fees: succeeded",
        "analyze-risk: skipped",
    ]


def test_investment_document_review_risk_assessment_result_accepts_structured_status() -> None:
    result = InvestmentDocumentReviewRiskAssessmentResult.model_validate(
        {
            "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH,
            "risk_reason": "Multiple unresolved disclosure gaps prevent automatic release.",
            "critical_issues": [
                "No benchmark methodology is provided.",
                "Fee disclosure is incomplete.",
            ],
            "approval_status": (
                InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL
            ),
            "required_role": COMPLIANCE_REVIEWER_ROLE,
            "auto_proceed": False,
        }
    )

    assert result.overall_risk is InvestmentDocumentReviewRiskLevel.HIGH
    assert (
        result.approval_status
        is InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL
    )
    assert result.required_role == COMPLIANCE_REVIEWER_ROLE
    assert result.auto_proceed is False


def test_investment_document_review_prompt_builds_messages() -> None:
    messages = build_prompt_messages(
        "tasks",
        "investment_document_review_single_pass.md",
        {
            "document_text": "This ETF tracks a broad market index.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["underlying index"],
            "analyze_focus": ["risk disclosures"],
            "review_goal": "Summarize major risks",
        },
    )

    assert len(messages) == 2
    assert "document_text" in messages[1].content
    assert "extract_focus" in messages[1].content
    assert "Summarize major risks" in messages[1].content
