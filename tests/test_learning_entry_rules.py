import pytest

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)
from investory.agent_core.runtime.flow.learning_entry_rules import (
    INSTRUMENT_NAME_OR_CODE_FIELD,
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    SOURCE_MATERIAL_FIELD,
    detect_missing_fields,
    infer_candidate_task_type,
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
