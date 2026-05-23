import pytest

from investory.agent_core.actions.validator import (
    ActionValidationError,
    validate_action_params,
    validate_decision,
    validate_decision_contract,
)
from investory.agent_core.contracts.action_contract import TaskDecision
from investory.agent_core.tasks import FINANCE_QA_TASK, INSTRUMENT_BRIEF_TASK


def test_validate_decision_builds_action_call_for_missing_fields():
    decision = TaskDecision(
        action="ask_missing_fields",
        task_name="instrument_brief",
        reason="The request is missing source material.",
        params={"missing_fields": ["source_material"]},
    )

    call = validate_decision(
        decision,
        INSTRUMENT_BRIEF_TASK,
        request_id="req_123",
    )

    assert call.action == "ask_missing_fields"
    assert call.task_name == "instrument_brief"
    assert call.params == {"missing_fields": ["source_material"]}
    assert call.decision_reason == "The request is missing source material."
    assert call.request_id == "req_123"


def test_validate_decision_rejects_task_name_mismatch():
    decision = TaskDecision(
        action="run_task_model",
        task_name="instrument_brief",
        reason="Ready to run.",
        params={"payload": {}},
    )

    with pytest.raises(ActionValidationError, match="does not match"):
        validate_decision(decision, FINANCE_QA_TASK)


def test_validate_decision_rejects_empty_missing_fields():
    decision = TaskDecision(
        action="ask_missing_fields",
        task_name="instrument_brief",
        reason="Missing required fields.",
        params={"missing_fields": []},
    )

    with pytest.raises(ActionValidationError, match="missing_fields"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_rejects_missing_fields_outside_input_model():
    decision = TaskDecision(
        action="ask_missing_fields",
        task_name="instrument_brief",
        reason="Missing required fields.",
        params={"missing_fields": ["unknown_field"]},
    )

    with pytest.raises(ActionValidationError, match="not defined"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_rejects_missing_fields_with_non_string_item():
    decision = TaskDecision(
        action="ask_missing_fields",
        task_name="instrument_brief",
        reason="Missing required fields.",
        params={"missing_fields": ["source_material", 123]},
    )

    with pytest.raises(ActionValidationError, match="only strings"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_accepts_run_task_model_with_payload():
    decision = TaskDecision(
        action="run_task_model",
        task_name="instrument_brief",
        reason="The payload contains all required fields.",
        params={
            "payload": {
                "instrument_name_or_code": "VOO",
                "source_material": "VOO tracks a broad US equity index.",
            }
        },
    )

    call = validate_decision(decision, INSTRUMENT_BRIEF_TASK)

    assert call.action == "run_task_model"
    assert call.params["payload"]["instrument_name_or_code"] == "VOO"


def test_validate_decision_accepts_run_tool_with_payload():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need instrument profile source material before model execution.",
        params={
            "tool_name": "lookup_instrument_profile",
            "payload": {"instrument_name_or_code": "VOO"},
        },
    )

    call = validate_decision(decision, INSTRUMENT_BRIEF_TASK)

    assert call.action == "run_tool"
    assert call.params == {
        "tool_name": "lookup_instrument_profile",
        "payload": {"instrument_name_or_code": "VOO"},
    }


def test_validate_decision_rejects_run_task_model_without_payload():
    decision = TaskDecision(
        action="run_task_model",
        task_name="instrument_brief",
        reason="Ready to run.",
    )

    with pytest.raises(ActionValidationError, match="payload"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_rejects_run_tool_without_tool_name():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need tool data before running the model.",
        params={"payload": {"instrument_name_or_code": "VOO"}},
    )

    with pytest.raises(ActionValidationError, match="tool_name"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


@pytest.mark.parametrize("tool_name", ["", "   ", 123])
def test_validate_decision_rejects_run_tool_with_invalid_tool_name(tool_name):
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need tool data before running the model.",
        params={
            "tool_name": tool_name,
            "payload": {"instrument_name_or_code": "VOO"},
        },
    )

    with pytest.raises(ActionValidationError, match="tool_name"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_rejects_run_tool_without_payload():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need tool data before running the model.",
        params={"tool_name": "lookup_instrument_profile"},
    )

    with pytest.raises(ActionValidationError, match="payload"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_accepts_refuse_with_user_message():
    decision = TaskDecision(
        action="refuse_investment_advice",
        task_name="instrument_brief",
        reason="The request asks for a buy or sell decision.",
        params={"allowed_alternative": "I can help create an educational brief."},
        user_message="I cannot decide whether you should buy or sell.",
    )

    call = validate_decision(decision, INSTRUMENT_BRIEF_TASK)

    assert call.action == "refuse_investment_advice"
    assert call.params["allowed_alternative"] == (
        "I can help create an educational brief."
    )


def test_validate_decision_accepts_refuse_with_refused_reason():
    decision = TaskDecision(
        action="refuse_investment_advice",
        task_name="instrument_brief",
        reason="The request asks for a buy or sell decision.",
        params={"refused_reason": "The system does not provide investment advice."},
    )

    call = validate_decision(decision, INSTRUMENT_BRIEF_TASK)

    assert call.action == "refuse_investment_advice"


def test_validate_decision_rejects_refuse_without_message_or_reason():
    decision = TaskDecision(
        action="refuse_investment_advice",
        task_name="instrument_brief",
        reason="The request asks for a buy or sell decision.",
    )

    with pytest.raises(ActionValidationError, match="user_message or refused_reason"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_rejects_unsupported_action_from_unvalidated_model():
    decision = TaskDecision.model_construct(
        action="unknown_action",
        task_name="instrument_brief",
        reason="Bypassed pydantic validation.",
        params={},
        user_message=None,
        need_user_confirmation=False,
        confidence=1.0,
    )

    with pytest.raises(ActionValidationError, match="Unsupported action"):
        validate_decision(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_decision_contract_skips_action_specific_param_validation():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Ready to run.",
        # intentionally missing tool_name and payload
    )

    call = validate_decision_contract(decision, INSTRUMENT_BRIEF_TASK)

    assert call.action == "run_tool"
    assert call.params == {}


def test_validate_action_params_rejects_run_task_model_without_payload():
    decision = TaskDecision(
        action="run_task_model",
        task_name="instrument_brief",
        reason="Ready to run.",
    )

    with pytest.raises(ActionValidationError, match="payload"):
        validate_action_params(decision, INSTRUMENT_BRIEF_TASK)


def test_validate_action_params_rejects_run_tool_without_payload():
    decision = TaskDecision(
        action="run_tool",
        task_name="instrument_brief",
        reason="Need tool data before running the model.",
        params={"tool_name": "lookup_instrument_profile"},
    )

    with pytest.raises(ActionValidationError, match="payload"):
        validate_action_params(decision, INSTRUMENT_BRIEF_TASK)
