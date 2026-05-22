from investory.agent_core.actions.validator import validate_decision
from investory.agent_core.runtime.flow.decision_planner import (
    DecisionPlanner,
    build_task_decision,
)
from investory.agent_core.tasks import FINANCE_QA_TASK, INSTRUMENT_BRIEF_TASK


def test_decision_planner_returns_missing_fields_decision():
    decision = DecisionPlanner().decide(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
    )

    assert decision.action == "ask_missing_fields"
    assert decision.task_name == "instrument_brief"
    assert decision.params == {"missing_fields": ["source_material"]}
    assert "source_material" in decision.reason
    assert decision.user_message is not None
    assert "source material" in decision.user_message


def test_decision_planner_treats_blank_required_strings_as_missing():
    decision = DecisionPlanner().decide(
        FINANCE_QA_TASK,
        {
            "material_text": "ETF is a basket of assets.",
            "question": "  ",
        },
    )

    assert decision.action == "ask_missing_fields"
    assert decision.task_name == "finance_qa"
    assert decision.params == {"missing_fields": ["question"]}


def test_decision_planner_returns_run_task_model_decision_for_complete_payload():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }

    decision = DecisionPlanner().decide(INSTRUMENT_BRIEF_TASK, payload)

    assert decision.action == "run_task_model"
    assert decision.task_name == "instrument_brief"
    assert decision.params == {"payload": payload}
    assert decision.user_message is None
    assert decision.reason == (
        "The request contains all required input fields for instrument_brief."
    )


def test_decision_planner_copies_payload_into_run_task_model_params():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }

    decision = DecisionPlanner().decide(INSTRUMENT_BRIEF_TASK, payload)
    payload["source_material"] = "Changed after planning."

    assert decision.params["payload"] == {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }


def test_build_task_decision_uses_default_planner():
    decision = build_task_decision(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
    )

    assert decision.action == "ask_missing_fields"
    assert decision.params == {"missing_fields": ["source_material"]}


def test_decision_planner_output_can_be_validated_into_action_call():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }
    decision = DecisionPlanner().decide(INSTRUMENT_BRIEF_TASK, payload)

    call = validate_decision(decision, INSTRUMENT_BRIEF_TASK, request_id="req_123")

    assert call.action == "run_task_model"
    assert call.params == {"payload": payload}
    assert call.decision_reason == decision.reason
    assert call.request_id == "req_123"
