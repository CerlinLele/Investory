import pytest

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
from investory.agent_core.task_models.investment_document_review_reflection import (
    InvestmentDocumentReviewReflectionCritique,
    InvestmentDocumentReviewReflectionInput,
    InvestmentDocumentReviewReflectionResult,
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


def test_investment_document_review_risk_assessment_result_rejects_inconsistent_critical_issues_and_auto_approved() -> None:
    with pytest.raises(ValueError, match="critical_issues present but approval_status is auto_approved"):
        InvestmentDocumentReviewRiskAssessmentResult.model_validate(
            {
                "overall_risk": InvestmentDocumentReviewRiskLevel.LOW,
                "risk_reason": "No significant risks found.",
                "critical_issues": ["This should not exist"],
                "approval_status": InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED,
                "required_role": None,
                "auto_proceed": True,
            }
        )


def test_investment_document_review_risk_assessment_result_rejects_pending_approval_without_critical_issues() -> None:
    with pytest.raises(ValueError, match="approval_status is pending_human_approval but critical_issues is empty"):
        InvestmentDocumentReviewRiskAssessmentResult.model_validate(
            {
                "overall_risk": InvestmentDocumentReviewRiskLevel.MEDIUM,
                "risk_reason": "Some concerns present.",
                "critical_issues": [],
                "approval_status": InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL,
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            }
        )


def test_investment_document_review_risk_assessment_result_rejects_high_risk_without_critical_issues() -> None:
    with pytest.raises(ValueError, match="high risk requires at least one critical_issue"):
        InvestmentDocumentReviewRiskAssessmentResult.model_validate(
            {
                "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH,
                "risk_reason": "High risk assessment.",
                "critical_issues": [],
                "approval_status": InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL,
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            }
        )


def test_investment_document_review_risk_assessment_result_rejects_auto_proceed_true_with_pending_approval() -> None:
    with pytest.raises(ValueError, match="auto_proceed cannot be true when approval_status is pending_human_approval"):
        InvestmentDocumentReviewRiskAssessmentResult.model_validate(
            {
                "overall_risk": InvestmentDocumentReviewRiskLevel.MEDIUM,
                "risk_reason": "Some concerns present.",
                "critical_issues": ["Incomplete disclosure"],
                "approval_status": InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL,
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": True,
            }
        )



def test_investment_document_review_reflection_input_defaults_and_limits() -> None:
    payload = InvestmentDocumentReviewReflectionInput.model_validate(
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_confidence": 0.88,
            "review_goal": "Check fees and boundaries",
            "review_result": {
                "document_type": InvestmentDocumentType.ETF_FACTSHEET,
                "extracted_facts": ["The factsheet lists a 0.10% fee."],
                "risk_findings": ["Fee disclosure is present."],
                "information_gaps": [],
                "boundary_notes": ["This review is not investment advice."],
                "summary": "Fee disclosure is clear from the provided document.",
            },
            "criteria": ["No investment advice.", "Facts must be supported."],
        }
    )

    assert payload.max_rounds == 1
    assert payload.todo_results == []
    assert payload.review_result.document_type is InvestmentDocumentType.ETF_FACTSHEET


def test_investment_document_review_reflection_validation_enforces_bounds() -> None:
    valid_critique = InvestmentDocumentReviewReflectionCritique.model_validate(
        {
            "passed": True,
            "score": 1.0,
            "issues": [],
            "suggestions": [],
        }
    )
    valid_result = InvestmentDocumentReviewReflectionResult.model_validate(
        {
            "review_result": {
                "document_type": InvestmentDocumentType.FUND_PROSPECTUS,
                "extracted_facts": ["The prospectus discloses liquidity risk."],
                "risk_findings": ["Liquidity risk is disclosed."],
                "information_gaps": [],
                "boundary_notes": ["No buy, sell, or hold advice is provided."],
                "summary": "The review remains grounded in disclosed risks.",
            },
            "passed": True,
            "score": 0.9,
            "issues": [],
            "suggestions": ["Kept the summary concise."],
            "rounds": 1,
        }
    )

    assert valid_critique.safety_flags == []
    assert (
        valid_result.review_result.document_type
        is InvestmentDocumentType.FUND_PROSPECTUS
    )
    assert valid_result.safety_flags == []

    with pytest.raises(ValueError):
        InvestmentDocumentReviewReflectionCritique.model_validate(
            {
                "passed": False,
                "score": 1.1,
                "issues": ["Score is out of range."],
                "suggestions": [],
            }
        )

    with pytest.raises(ValueError):
        InvestmentDocumentReviewReflectionInput.model_validate(
            {
                "document_type": InvestmentDocumentType.ETF_FACTSHEET,
                "route_confidence": 0.88,
                "review_result": valid_result.review_result,
                "criteria": ["Facts must be supported."],
                "max_rounds": 3,
            }
        )


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


def test_investment_document_review_reflection_prompt_builds_messages() -> None:
    messages = build_prompt_messages(
        "tasks",
        "investment_document_review_reflection.md",
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_confidence": 0.88,
            "review_goal": "Check fee evidence",
            "review_result": {
                "document_type": InvestmentDocumentType.ETF_FACTSHEET,
                "extracted_facts": ["The factsheet lists a 0.10% fee."],
                "risk_findings": ["Fee disclosure is present."],
                "information_gaps": [],
                "boundary_notes": ["This review is not investment advice."],
                "summary": "Fee disclosure is clear from the provided document.",
            },
            "criteria": ["Facts must be supported."],
            "max_rounds": 1,
        },
    )

    assert len(messages) == 2
    assert "review_result" in messages[1].content
    assert "Facts must be supported." in messages[1].content
