import pytest
from pydantic import ValidationError

from investory.agent_core.contracts import (
    DOCUMENT_TEXT_FIELD,
    DOCUMENT_TYPE_HINT_FIELD,
    REVIEW_GOAL_FIELD,
    DocumentReviewFramework,
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)


@pytest.mark.parametrize(
    ("document_type", "expected_value"),
    [
        (InvestmentDocumentType.ETF_FACTSHEET, "etf_factsheet"),
        (InvestmentDocumentType.FUND_PROSPECTUS, "fund_prospectus"),
        (InvestmentDocumentType.PRODUCT_BROCHURE, "product_brochure"),
        (InvestmentDocumentType.EARNINGS_REPORT, "earnings_report"),
        (InvestmentDocumentType.LEARNING_MATERIAL, "learning_material"),
        (InvestmentDocumentType.UNKNOWN, "unknown"),
    ],
)
def test_investment_document_type_exposes_expected_values(
    document_type: InvestmentDocumentType,
    expected_value: str,
):
    assert document_type.value == expected_value


def test_investment_document_review_route_decision_validates_confidence_bounds():
    decision = InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.ETF_FACTSHEET,
        confidence=0.75,
        reason="The excerpt references ETF holdings and fee ratios.",
    )

    assert decision.document_type is InvestmentDocumentType.ETF_FACTSHEET
    assert decision.confidence == 0.75
    assert decision.missing_fields == []


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_investment_document_review_route_decision_rejects_out_of_range_confidence(
    confidence: float,
):
    with pytest.raises(ValidationError):
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.UNKNOWN,
            confidence=confidence,
            reason="Unable to determine the document type with confidence.",
        )


def test_investment_document_review_state_defaults_to_expected_empty_values():
    state = InvestmentDocumentReviewState(
        input_payload={
            DOCUMENT_TEXT_FIELD: "Example document text",
            DOCUMENT_TYPE_HINT_FIELD: "fund prospectus",
            REVIEW_GOAL_FIELD: "Extract key risks",
        },
    )

    assert state.session_id is None
    assert state.input_payload[DOCUMENT_TEXT_FIELD] == "Example document text"
    assert state.missing_fields == []
    assert state.document_type is None
    assert state.route_reason is None
    assert state.route_confidence is None
    assert state.review_framework is None
    assert state.review_payload is None
    assert state.output is None


def test_investment_document_review_state_requires_input_payload():
    with pytest.raises(ValidationError) as exc_info:
        InvestmentDocumentReviewState()

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}

    assert missing_fields == {"input_payload"}


def test_document_review_framework_defaults_to_empty_lists():
    framework = DocumentReviewFramework()

    assert framework.extract_focus == []
    assert framework.analyze_focus == []
