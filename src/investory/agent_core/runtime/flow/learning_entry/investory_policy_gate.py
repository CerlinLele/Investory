from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investory.agent_core.runtime.flow.learning_entry.investory_actions import InvestoryAction
from investory.agent_core.runtime.flow.learning_entry.learning_entry_router import (
    LearningEntryRoute,
    LearningEntryRouteDecision,
    LearningEntryRouter,
    candidate_task_type_for_route,
)
from investory.agent_core.runtime.flow.learning_entry.learning_entry_rules import (
    CONFIRMATION_GRANTED_FIELD,
    UNKNOWN_INPUT_MISSING_FIELDS,
    detect_missing_fields,
    has_user_confirmation,
    infer_candidate_task_type,
    looks_like_investment_advice,
    requires_realtime_data,
    requires_user_confirmation,
)


CANDIDATE_TASK_TYPE_METADATA_KEY = "candidate_task_type"
ROUTE_METADATA_KEY = "route"
ROUTE_CONFIDENCE_METADATA_KEY = "route_confidence"
ROUTE_REASON_METADATA_KEY = "route_reason"
DEFAULT_ROUTE_CONFIDENCE_THRESHOLD = 0.6


class InvestoryPolicyReason(str, Enum):
    MISSING_REQUIRED_INPUT = "missing_required_input"
    INVESTMENT_ADVICE_REQUEST = "investment_advice_request"
    REALTIME_DATA_NOT_AVAILABLE = "realtime_data_not_available"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    LOW_CONFIDENCE_ROUTE = "low_confidence_route"
    READY_TO_EXECUTE = "ready_to_execute"


class InvestoryPolicyInput(BaseModel):
    payload: dict[str, Any]
    supports_realtime_data: bool = False


class InvestoryPolicyResult(BaseModel):
    action: InvestoryAction
    reason: InvestoryPolicyReason
    missing_fields: list[str] = Field(default_factory=list)
    requires_realtime_data: bool = False
    requires_user_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestoryPolicyGate:
    def __init__(
        self,
        llm_router: LearningEntryRouter | None = None,
        *,
        route_confidence_threshold: float = DEFAULT_ROUTE_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.llm_router = llm_router
        self.route_confidence_threshold = route_confidence_threshold

    def evaluate(self, policy_input: InvestoryPolicyInput) -> InvestoryPolicyResult:
        payload = policy_input.payload

        missing_fields = detect_missing_fields(payload)
        if missing_fields:
            return InvestoryPolicyResult(
                action=InvestoryAction.ASK_FOR_MISSING_INPUT,
                reason=InvestoryPolicyReason.MISSING_REQUIRED_INPUT,
                missing_fields=missing_fields,
            )

        if looks_like_investment_advice(payload):
            return InvestoryPolicyResult(
                action=InvestoryAction.REFUSE_AND_REDIRECT,
                reason=InvestoryPolicyReason.INVESTMENT_ADVICE_REQUEST,
            )

        needs_realtime_data = requires_realtime_data(payload)
        if needs_realtime_data and not policy_input.supports_realtime_data:
            return InvestoryPolicyResult(
                action=InvestoryAction.REFUSE_AND_REDIRECT,
                reason=InvestoryPolicyReason.REALTIME_DATA_NOT_AVAILABLE,
                requires_realtime_data=True,
            )

        needs_user_confirmation = requires_user_confirmation(payload)
        if needs_user_confirmation and not has_user_confirmation(payload):
            return InvestoryPolicyResult(
                action=InvestoryAction.ASK_FOR_MISSING_INPUT,
                reason=InvestoryPolicyReason.USER_CONFIRMATION_REQUIRED,
                missing_fields=[CONFIRMATION_GRANTED_FIELD],
                requires_user_confirmation=True,
            )

        candidate_task_type = infer_candidate_task_type(payload)
        if candidate_task_type is None:
            if self.llm_router is not None:
                return self._evaluate_llm_route(payload)

            return InvestoryPolicyResult(
                action=InvestoryAction.ASK_FOR_MISSING_INPUT,
                reason=InvestoryPolicyReason.MISSING_REQUIRED_INPUT,
                missing_fields=list(UNKNOWN_INPUT_MISSING_FIELDS),
            )

        return InvestoryPolicyResult(
            action=InvestoryAction.EXECUTE_LEARNING_TASK,
            reason=InvestoryPolicyReason.READY_TO_EXECUTE,
            requires_realtime_data=needs_realtime_data,
            requires_user_confirmation=needs_user_confirmation,
            metadata={
                CANDIDATE_TASK_TYPE_METADATA_KEY: (
                    candidate_task_type.value if candidate_task_type is not None else None
                )
            },
        )

    def _evaluate_llm_route(self, payload: dict[str, Any]) -> InvestoryPolicyResult:
        if self.llm_router is None:
            raise RuntimeError("LLM router is not configured.")

        route_decision = self.llm_router.route(payload)
        metadata = self._route_metadata(route_decision)

        if self._should_fallback_for_low_confidence(route_decision):
            return InvestoryPolicyResult(
                action=InvestoryAction.ASK_FOR_MISSING_INPUT,
                reason=InvestoryPolicyReason.LOW_CONFIDENCE_ROUTE,
                metadata=metadata,
            )

        candidate_task_type = candidate_task_type_for_route(route_decision.route)

        if candidate_task_type is not None:
            metadata[CANDIDATE_TASK_TYPE_METADATA_KEY] = candidate_task_type.value
            return InvestoryPolicyResult(
                action=InvestoryAction.EXECUTE_LEARNING_TASK,
                reason=InvestoryPolicyReason.READY_TO_EXECUTE,
                metadata=metadata,
            )

        if route_decision.route == LearningEntryRoute.REFUSE_AND_REDIRECT:
            return InvestoryPolicyResult(
                action=InvestoryAction.REFUSE_AND_REDIRECT,
                reason=InvestoryPolicyReason.INVESTMENT_ADVICE_REQUEST,
                metadata=metadata,
            )

        return InvestoryPolicyResult(
            action=InvestoryAction.ASK_FOR_MISSING_INPUT,
            reason=InvestoryPolicyReason.MISSING_REQUIRED_INPUT,
            missing_fields=route_decision.missing_fields
            or list(UNKNOWN_INPUT_MISSING_FIELDS),
            metadata=metadata,
        )

    @staticmethod
    def _route_metadata(
        route_decision: LearningEntryRouteDecision,
    ) -> dict[str, Any]:
        return {
            ROUTE_METADATA_KEY: route_decision.route.value,
            ROUTE_CONFIDENCE_METADATA_KEY: route_decision.confidence,
            ROUTE_REASON_METADATA_KEY: route_decision.reason,
        }

    def _should_fallback_for_low_confidence(
        self,
        route_decision: LearningEntryRouteDecision,
    ) -> bool:
        return (
            route_decision.confidence < self.route_confidence_threshold
            or route_decision.route == LearningEntryRoute.GENERAL_LEARNING_CLARIFICATION
        )
