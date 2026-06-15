from typing import TYPE_CHECKING, Any, Protocol

from investory.agent_core.contracts.investment_document_review_state import (
    DOCUMENT_TYPE_HINT_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentType,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    DEFAULT_DOCUMENT_ROUTE_CONFIDENCE_THRESHOLD,
    UNKNOWN_DOCUMENT_MISSING_FIELDS,
    build_document_excerpt,
)
from investory.agent_core.runtime.message_builder import build_prompt_messages

if TYPE_CHECKING:
    from investory.agent_core.runtime.request_runner import RequestRunner


INVESTMENT_DOCUMENT_REVIEW_ROUTER_PROMPT_FILE = (
    "investment_document_review_router.md"
)
DOCUMENT_EXCERPT_FIELD = "document_excerpt"


class InvestmentDocumentReviewRouter(Protocol):
    def route(self, payload: dict[str, Any]) -> InvestmentDocumentReviewRouteDecision:
        """Return a structured document-review routing decision."""


def normalize_route_decision(
    decision: InvestmentDocumentReviewRouteDecision,
) -> InvestmentDocumentReviewRouteDecision:
    if decision.confidence >= DEFAULT_DOCUMENT_ROUTE_CONFIDENCE_THRESHOLD:
        return decision

    missing_fields = list(decision.missing_fields)
    if not missing_fields:
        missing_fields = list(UNKNOWN_DOCUMENT_MISSING_FIELDS)

    return InvestmentDocumentReviewRouteDecision(
        document_type=InvestmentDocumentType.UNKNOWN,
        confidence=decision.confidence,
        reason=decision.reason,
        missing_fields=missing_fields,
    )


class InvestmentDocumentReviewLLMRouter:
    def __init__(self, runner: "RequestRunner | None" = None) -> None:
        if runner is None:
            from investory.agent_core.runtime.request_runner import RequestRunner

            runner = RequestRunner()
        self.runner = runner

    def route(self, payload: dict[str, Any]) -> InvestmentDocumentReviewRouteDecision:
        router_payload = {
            DOCUMENT_EXCERPT_FIELD: build_document_excerpt(payload),
            DOCUMENT_TYPE_HINT_FIELD: payload.get(DOCUMENT_TYPE_HINT_FIELD),
            REVIEW_GOAL_FIELD: payload.get(REVIEW_GOAL_FIELD),
        }
        messages = build_prompt_messages(
            "flows",
            INVESTMENT_DOCUMENT_REVIEW_ROUTER_PROMPT_FILE,
            router_payload,
        )

        decision = self.runner.run(messages, InvestmentDocumentReviewRouteDecision)
        return normalize_route_decision(decision)
