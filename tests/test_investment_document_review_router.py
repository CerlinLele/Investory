from typing import Any

from pydantic import BaseModel

from investory.agent_core.contracts.investment_document_review_state import (
    DOCUMENT_TYPE_HINT_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentType,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_router import (
    DOCUMENT_EXCERPT_FIELD,
    InvestmentDocumentReviewLLMRouter,
    normalize_route_decision,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    DOCUMENT_ROUTER_MAX_CHARS,
    UNKNOWN_DOCUMENT_MISSING_FIELDS,
)


class FakeRunner:
    def __init__(self, result: InvestmentDocumentReviewRouteDecision) -> None:
        self.result = result
        self.messages: list[Any] | None = None
        self.output_model: type[BaseModel] | None = None

    def run(
        self,
        messages: list[Any],
        output_model: type[BaseModel],
    ) -> BaseModel:
        self.messages = messages
        self.output_model = output_model
        return self.result


def test_investment_document_review_llm_router_uses_route_decision_model() -> None:
    expected_result = InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.ETF_FACTSHEET,
        confidence=0.87,
        reason="The excerpt describes index tracking and expense ratios.",
    )
    runner = FakeRunner(expected_result)
    router = InvestmentDocumentReviewLLMRouter(runner=runner)

    result = router.route({DOCUMENT_EXCERPT_FIELD: "ignored"})

    assert result is expected_result
    assert runner.output_model is InvestmentDocumentReviewRouteDecision
    assert runner.messages is not None


def test_investment_document_review_llm_router_uses_document_excerpt_not_full_text() -> None:
    long_document = "a" * (DOCUMENT_ROUTER_MAX_CHARS + 50)
    runner = FakeRunner(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.LEARNING_MATERIAL,
            confidence=0.82,
            reason="Looks like educational content.",
        )
    )
    router = InvestmentDocumentReviewLLMRouter(runner=runner)

    router.route({"document_text": long_document})

    assert runner.messages is not None
    content = runner.messages[1].content
    assert DOCUMENT_EXCERPT_FIELD in content
    assert '"document_text"' not in content
    assert "a" * DOCUMENT_ROUTER_MAX_CHARS in content
    assert "a" * (DOCUMENT_ROUTER_MAX_CHARS + 1) not in content


def test_investment_document_review_llm_router_includes_hint_and_review_goal() -> None:
    runner = FakeRunner(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.FUND_PROSPECTUS,
            confidence=0.9,
            reason="The hint and excerpt align with a prospectus.",
        )
    )
    router = InvestmentDocumentReviewLLMRouter(runner=runner)

    router.route(
        {
            "document_text": "Fund terms and redemption rules.",
            DOCUMENT_TYPE_HINT_FIELD: "fund_prospectus",
            REVIEW_GOAL_FIELD: "Check risks and fees",
        }
    )

    assert runner.messages is not None
    content = runner.messages[1].content
    assert "fund_prospectus" in content
    assert "Check risks and fees" in content


def test_normalize_route_decision_preserves_known_high_confidence_result() -> None:
    decision = InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.PRODUCT_BROCHURE,
        confidence=0.78,
        reason="Clear product marketing language.",
    )

    assert normalize_route_decision(decision) is decision


def test_normalize_route_decision_downgrades_low_confidence_to_unknown() -> None:
    decision = InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.EARNINGS_REPORT,
        confidence=0.42,
        reason="The excerpt is too weak to classify safely.",
    )

    normalized = normalize_route_decision(decision)

    assert normalized.document_type is InvestmentDocumentType.UNKNOWN
    assert normalized.confidence == 0.42
    assert normalized.reason == decision.reason
    assert normalized.missing_fields == UNKNOWN_DOCUMENT_MISSING_FIELDS


def test_normalize_route_decision_preserves_missing_fields_on_downgrade() -> None:
    decision = InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.FUND_PROSPECTUS,
        confidence=0.5,
        reason="Need stronger type guidance.",
        missing_fields=[DOCUMENT_TYPE_HINT_FIELD],
    )

    normalized = normalize_route_decision(decision)

    assert normalized.document_type is InvestmentDocumentType.UNKNOWN
    assert normalized.missing_fields == [DOCUMENT_TYPE_HINT_FIELD]
