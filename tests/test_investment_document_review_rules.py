from datetime import datetime, timezone

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
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE,
    DOCUMENT_ROUTER_MAX_CHARS,
    UNKNOWN_DOCUMENT_MISSING_FIELDS,
    build_document_excerpt,
    detect_missing_fields,
    get_review_framework,
    looks_like_investment_advice,
    requires_realtime_data,
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
    assert state.reflection_result is None
    assert state.reflection_passed is None
    assert state.reflection_rounds is None
    assert state.risk_assessment is None
    assert state.approval_status is None
    assert state.approval_required_role is None
    assert state.approval_decision_at is None
    assert state.approval_actor_role is None
    assert state.output is None


def test_investment_document_review_state_requires_input_payload():
    with pytest.raises(ValidationError) as exc_info:
        InvestmentDocumentReviewState()

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}

    assert missing_fields == {"input_payload"}


def test_investment_document_review_state_accepts_future_approval_resume_fields():
    decided_at = datetime(2026, 6, 12, 10, 30, tzinfo=timezone.utc)

    state = InvestmentDocumentReviewState(
        input_payload={DOCUMENT_TEXT_FIELD: "Example document text"},
        approval_status="pending_human_approval",
        approval_required_role="compliance_reviewer",
        approval_decision_at=decided_at,
        approval_actor_role="compliance_reviewer",
    )

    assert state.approval_status == "pending_human_approval"
    assert state.approval_required_role == "compliance_reviewer"
    assert state.approval_decision_at == decided_at
    assert state.approval_actor_role == "compliance_reviewer"


def test_document_review_framework_defaults_to_empty_lists():
    framework = DocumentReviewFramework()

    assert framework.extract_focus == []
    assert framework.analyze_focus == []


def test_detect_missing_fields_returns_document_text_when_absent():
    assert detect_missing_fields({}) == [DOCUMENT_TEXT_FIELD]
    assert detect_missing_fields({DOCUMENT_TEXT_FIELD: "   "}) == [DOCUMENT_TEXT_FIELD]


def test_detect_missing_fields_returns_empty_when_document_text_exists():
    payload = {DOCUMENT_TEXT_FIELD: "ETF factsheet content"}
    assert detect_missing_fields(payload) == []


def test_unknown_document_missing_fields_requests_document_type_hint():
    assert UNKNOWN_DOCUMENT_MISSING_FIELDS == [DOCUMENT_TYPE_HINT_FIELD]


def test_looks_like_investment_advice_detects_review_goal_intent():
    payload = {REVIEW_GOAL_FIELD: "Please tell me whether I should buy now."}
    assert looks_like_investment_advice(payload) is True


def test_looks_like_investment_advice_ignores_document_text_keywords_only():
    payload = {
        DOCUMENT_TEXT_FIELD: "This brochure compares buy and sell scenarios historically.",
        REVIEW_GOAL_FIELD: "Summarize key disclosures only.",
    }
    assert looks_like_investment_advice(payload) is False


def test_looks_like_investment_advice_does_not_treat_holdings_as_hold_intent():
    payload = {
        REVIEW_GOAL_FIELD: (
            "Review fee clarity, risk disclosure, holdings, yield-related metrics, "
            "and performance limitations."
        )
    }
    assert looks_like_investment_advice(payload) is False


def test_requires_realtime_data_detects_review_goal_intent():
    payload = {REVIEW_GOAL_FIELD: "Use this material and give me today's price impact."}
    assert requires_realtime_data(payload) is True


def test_requires_realtime_data_ignores_document_text_historical_dates():
    payload = {
        DOCUMENT_TEXT_FIELD: "Latest quarterly report for Q4 2025 with dated notes.",
        REVIEW_GOAL_FIELD: "Summarize risks and assumptions.",
    }
    assert requires_realtime_data(payload) is False


def test_build_document_excerpt_truncates_to_max_chars():
    payload = {DOCUMENT_TEXT_FIELD: "a" * (DOCUMENT_ROUTER_MAX_CHARS + 50)}
    excerpt = build_document_excerpt(payload)
    assert len(excerpt) == DOCUMENT_ROUTER_MAX_CHARS
    assert excerpt == "a" * DOCUMENT_ROUTER_MAX_CHARS


def test_each_known_document_type_has_review_framework():
    for document_type in (
        InvestmentDocumentType.ETF_FACTSHEET,
        InvestmentDocumentType.FUND_PROSPECTUS,
        InvestmentDocumentType.PRODUCT_BROCHURE,
        InvestmentDocumentType.EARNINGS_REPORT,
        InvestmentDocumentType.LEARNING_MATERIAL,
    ):
        framework = get_review_framework(document_type)
        assert framework is not None
        assert framework == DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE[document_type]
        assert framework.extract_focus
        assert framework.analyze_focus


def test_unknown_document_type_does_not_resolve_framework():
    assert get_review_framework(InvestmentDocumentType.UNKNOWN) is None
