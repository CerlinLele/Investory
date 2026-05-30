from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investory.agent_core.runtime.flow.investory_actions import InvestoryAction
from investory.agent_core.runtime.flow.learning_entry_rules import (
    CONFIRMATION_GRANTED_FIELD,
    UNKNOWN_INPUT_MISSING_FIELDS,
    detect_missing_fields,
    has_user_confirmation,
    infer_candidate_task_type,
    looks_like_investment_advice,
    requires_realtime_data,
    requires_user_confirmation,
)


class InvestoryPolicyReason(str, Enum):
    MISSING_REQUIRED_INPUT = "missing_required_input"
    INVESTMENT_ADVICE_REQUEST = "investment_advice_request"
    REALTIME_DATA_NOT_AVAILABLE = "realtime_data_not_available"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
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
    def evaluate(self, policy_input: InvestoryPolicyInput) -> InvestoryPolicyResult:
        payload = policy_input.payload

        missing_fields = detect_missing_fields(payload)
        candidate_task_type = infer_candidate_task_type(payload)
        if candidate_task_type is None and not missing_fields:
            missing_fields = list(UNKNOWN_INPUT_MISSING_FIELDS)
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

        return InvestoryPolicyResult(
            action=InvestoryAction.EXECUTE_LEARNING_TASK,
            reason=InvestoryPolicyReason.READY_TO_EXECUTE,
            requires_realtime_data=needs_realtime_data,
            requires_user_confirmation=needs_user_confirmation,
            metadata={
                "candidate_task_type": (
                    candidate_task_type.value if candidate_task_type is not None else None
                )
            },
        )
