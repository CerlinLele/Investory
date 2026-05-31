import pytest

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)
from investory.agent_core.runtime.flow.learning_entry_rules import (
    CONFIRMATION_GRANTED_FIELD,
    INSTRUMENT_NAME_OR_CODE_FIELD,
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    REQUIRES_CONFIRMATION_FIELD,
    REQUIRES_REALTIME_DATA_FIELD,
    SOURCE_MATERIAL_FIELD,
    detect_missing_fields,
    has_user_confirmation,
    infer_candidate_task_type,
    looks_like_investment_advice,
    requires_realtime_data,
    requires_user_confirmation,
)


def test_detect_missing_fields_for_qa_question_without_material():
    payload = {QUESTION_FIELD: "What is an ETF?"}

    assert detect_missing_fields(payload) == [MATERIAL_TEXT_FIELD]


def test_detect_missing_fields_for_brief_instrument_without_source_material():
    payload = {INSTRUMENT_NAME_OR_CODE_FIELD: "VOO"}

    assert detect_missing_fields(payload) == [SOURCE_MATERIAL_FIELD]


@pytest.mark.parametrize(
    ("payload", "expected_task_type"),
    [
        (
            {
                MATERIAL_TEXT_FIELD: "An ETF is a basket of assets.",
                QUESTION_FIELD: "What is an ETF?",
            },
            LearningEntryCandidateTaskType.QA,
        ),
        (
            {MATERIAL_TEXT_FIELD: "An ETF is a basket of assets."},
            LearningEntryCandidateTaskType.SUMMARY,
        ),
        (
            {
                INSTRUMENT_NAME_OR_CODE_FIELD: "VOO",
                SOURCE_MATERIAL_FIELD: "VOO tracks the S&P 500.",
            },
            LearningEntryCandidateTaskType.BRIEF,
        ),
    ],
)
def test_infer_candidate_task_type_for_complete_learning_inputs(
    payload,
    expected_task_type,
):
    assert infer_candidate_task_type(payload) == expected_task_type


def test_infer_candidate_task_type_returns_none_for_unknown_payload():
    assert infer_candidate_task_type({"topic": "ETF basics"}) is None


def test_looks_like_investment_advice_detects_advice_text():
    payload = {QUESTION_FIELD: "Should I buy VOO now?"}

    assert looks_like_investment_advice(payload) is True


def test_requires_realtime_data_detects_flag_and_text():
    assert requires_realtime_data({REQUIRES_REALTIME_DATA_FIELD: True}) is True
    assert requires_realtime_data({QUESTION_FIELD: "Need latest price for VOO"}) is True
    assert requires_realtime_data({QUESTION_FIELD: "Explain ETF basics"}) is False


def test_requires_user_confirmation_detects_flag_and_text():
    assert requires_user_confirmation({REQUIRES_CONFIRMATION_FIELD: True}) is True
    assert requires_user_confirmation({QUESTION_FIELD: "Please execute now"}) is True
    assert requires_user_confirmation({QUESTION_FIELD: "Explain ETF basics"}) is False


def test_has_user_confirmation_accepts_boolean_like_values():
    assert has_user_confirmation({CONFIRMATION_GRANTED_FIELD: True}) is True
    assert has_user_confirmation({CONFIRMATION_GRANTED_FIELD: "yes"}) is True
    assert has_user_confirmation({CONFIRMATION_GRANTED_FIELD: False}) is False
