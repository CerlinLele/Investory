import pytest
from pydantic import ValidationError

from investory.agent_core.contracts.action_contract import (
    ActionCall,
    ActionResult,
    TaskDecision,
)
from investory.agent_core.contracts.result_types import TaskError


def test_task_decision_accepts_supported_action_names():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need tool data before running the task model.",
        params={
            "tool_name": "lookup_instrument_profile",
            "payload": {"instrument_name_or_code": "VOO"},
        },
    )

    assert decision.action == "run_tool"
    assert decision.confidence == 1.0
    assert decision.user_message is None
    assert decision.need_user_confirmation is False


def test_task_decision_rejects_unknown_action_name():
    with pytest.raises(ValidationError):
        TaskDecision(
            action="unknown_action",
            task_name="instrument_brief",
            reason="Unsupported action.",
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_task_decision_rejects_confidence_outside_zero_to_one(confidence):
    with pytest.raises(ValidationError):
        TaskDecision(
            action="ask_missing_fields",
            task_name="instrument_brief",
            reason="Missing source material.",
            confidence=confidence,
        )


def test_action_call_captures_validated_system_call():
    call = ActionCall(
        action="ask_missing_fields",
        task_name="instrument_brief",
        params={"missing_fields": ["source_material"]},
        decision_reason="The request is missing source_material.",
        request_id="req_123",
    )

    assert call.model_dump() == {
        "action": "ask_missing_fields",
        "task_name": "instrument_brief",
        "params": {"missing_fields": ["source_material"]},
        "decision_reason": "The request is missing source_material.",
        "request_id": "req_123",
    }


@pytest.mark.parametrize(
    "status",
    ["success", "failed", "requires_user_input", "refused"],
)
def test_action_result_accepts_supported_statuses(status):
    result = ActionResult(
        action="run_task_model",
        task_name="instrument_brief",
        status=status,
        result={"ok": True},
    )

    assert result.status == status


def test_action_result_accepts_task_error_for_failed_action():
    error = TaskError(
        error_type="structured_output_failed",
        stage="output_validation",
        user_safe_message="The AI response did not match the required format.",
        retryable=True,
    )

    result = ActionResult(
        action="run_task_model",
        task_name="instrument_brief",
        status="failed",
        error=error,
    )

    assert result.result is None
    assert result.error == error
