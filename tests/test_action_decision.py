import pytest

from investory.agent_core.contracts.action_decision import (
    AskMissingFieldsAction,
    build_ask_missing_fields_action,
    decide_missing_fields_action,
)
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK


def test_build_ask_missing_fields_action_returns_stable_payload():
    action = build_ask_missing_fields_action(
        task_name="instrument_brief",
        missing_fields=["source_material"],
    )

    assert isinstance(action, AskMissingFieldsAction)
    assert action.model_dump() == {
        "action": "ask_missing_fields",
        "task_name": "instrument_brief",
        "missing_fields": ["source_material"],
        "user_message": (
            "Please paste the source material you want me to use, such as a fund "
            "description, ETF factsheet, news, or research excerpt."
        ),
        "reason": (
            "The request is missing required input fields for instrument_brief: "
            "source_material."
        ),
    }


def test_build_ask_missing_fields_action_rejects_empty_missing_fields():
    with pytest.raises(ValueError, match="missing_fields"):
        build_ask_missing_fields_action(
            task_name="instrument_brief",
            missing_fields=[],
        )


def test_decide_missing_fields_action_returns_none_when_payload_is_complete():
    action = decide_missing_fields_action(
        INSTRUMENT_BRIEF_TASK,
        {
            "instrument_name_or_code": "VOO",
            "source_material": "VOO tracks a broad US equity index.",
        },
    )

    assert action is None


def test_decide_missing_fields_action_returns_action_for_missing_payload():
    action = decide_missing_fields_action(INSTRUMENT_BRIEF_TASK, {})

    assert action is not None
    assert action.action == "ask_missing_fields"
    assert action.task_name == "instrument_brief"
    assert action.missing_fields == ["instrument_name_or_code", "source_material"]
    assert "instrument name or ticker/code" in action.user_message
