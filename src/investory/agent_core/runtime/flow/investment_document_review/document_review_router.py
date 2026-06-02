import json
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
from investory.agent_core.runtime.prompt_loader import load_prompt_text

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
        from langchain_core.prompts import ChatPromptTemplate

        router_payload = {
            DOCUMENT_EXCERPT_FIELD: build_document_excerpt(payload),
            DOCUMENT_TYPE_HINT_FIELD: payload.get(DOCUMENT_TYPE_HINT_FIELD),
            REVIEW_GOAL_FIELD: payload.get(REVIEW_GOAL_FIELD),
        }
        input_json = json.dumps(router_payload, ensure_ascii=False, indent=2)

        system_prompt = load_prompt_text("base", "system.md")
        common_rules = load_prompt_text("base", "common_rules.md")
        input_data_block = load_prompt_text("base", "input_data_block.md")
        router_prompt = load_prompt_text(
            "flows",
            INVESTMENT_DOCUMENT_REVIEW_ROUTER_PROMPT_FILE,
        )

        prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                ("human", router_prompt),
            ]
        )
        messages = prompt.invoke(
            {
                "common_rules": common_rules,
                "input_data_block": input_data_block.format(input_json=input_json),
            }
        ).messages

        decision = self.runner.run(messages, InvestmentDocumentReviewRouteDecision)
        return normalize_route_decision(decision)
