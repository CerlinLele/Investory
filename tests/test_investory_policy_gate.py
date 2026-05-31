import pytest

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)
from investory.agent_core.runtime.flow.investory_actions import InvestoryAction
from investory.agent_core.runtime.flow.investory_policy_gate import (
    CANDIDATE_TASK_TYPE_METADATA_KEY,
    InvestoryPolicyGate,
    InvestoryPolicyInput,
    InvestoryPolicyReason,
)
from investory.agent_core.runtime.flow.learning_entry_rules import (
    CONFIRMATION_GRANTED_FIELD,
    INSTRUMENT_NAME_OR_CODE_FIELD,
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    REQUIRES_CONFIRMATION_FIELD,
    REQUIRES_REALTIME_DATA_FIELD,
    SOURCE_MATERIAL_FIELD,
)


def test_policy_gate_asks_for_missing_input_when_fields_are_missing() -> None:
    gate = InvestoryPolicyGate()
    result = gate.evaluate(InvestoryPolicyInput(payload={QUESTION_FIELD: "What is ETF?"}))

    assert result.action == InvestoryAction.ASK_FOR_MISSING_INPUT
    assert result.reason == InvestoryPolicyReason.MISSING_REQUIRED_INPUT
    assert result.missing_fields == [MATERIAL_TEXT_FIELD]


def test_policy_gate_refuses_direct_investment_advice() -> None:
    gate = InvestoryPolicyGate()
    payload = {
        MATERIAL_TEXT_FIELD: "VOO tracks the S&P 500.",
        QUESTION_FIELD: "Should I buy VOO now?",
    }

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.REFUSE_AND_REDIRECT
    assert result.reason == InvestoryPolicyReason.INVESTMENT_ADVICE_REQUEST


def test_policy_gate_refuses_when_realtime_capability_is_missing() -> None:
    gate = InvestoryPolicyGate()
    payload = {
        MATERIAL_TEXT_FIELD: "ETF overview",
        QUESTION_FIELD: "Give me the latest price snapshot",
        REQUIRES_REALTIME_DATA_FIELD: True,
    }

    result = gate.evaluate(
        InvestoryPolicyInput(payload=payload, supports_realtime_data=False)
    )

    assert result.action == InvestoryAction.REFUSE_AND_REDIRECT
    assert result.reason == InvestoryPolicyReason.REALTIME_DATA_NOT_AVAILABLE
    assert result.requires_realtime_data is True


def test_policy_gate_requests_user_confirmation_when_required() -> None:
    gate = InvestoryPolicyGate()
    payload = {
        MATERIAL_TEXT_FIELD: "ETF overview",
        QUESTION_FIELD: "Summarize this content",
        REQUIRES_CONFIRMATION_FIELD: True,
    }

    result = gate.evaluate(
        InvestoryPolicyInput(payload=payload, supports_realtime_data=True)
    )

    assert result.action == InvestoryAction.ASK_FOR_MISSING_INPUT
    assert result.reason == InvestoryPolicyReason.USER_CONFIRMATION_REQUIRED
    assert result.missing_fields == [CONFIRMATION_GRANTED_FIELD]
    assert result.requires_user_confirmation is True


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
                SOURCE_MATERIAL_FIELD: "VOO tracks the S&P 500 index.",
            },
            LearningEntryCandidateTaskType.BRIEF,
        ),
    ],
)
def test_policy_gate_preserves_rule_routing_for_complete_learning_payloads(
    payload,
    expected_task_type,
) -> None:
    gate = InvestoryPolicyGate()

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.EXECUTE_LEARNING_TASK
    assert result.reason == InvestoryPolicyReason.READY_TO_EXECUTE
    assert result.metadata[CANDIDATE_TASK_TYPE_METADATA_KEY] == expected_task_type.value


def test_policy_gate_executes_learning_task_for_valid_learning_payload() -> None:
    gate = InvestoryPolicyGate()
    payload = {
        INSTRUMENT_NAME_OR_CODE_FIELD: "VOO",
        SOURCE_MATERIAL_FIELD: "VOO tracks the S&P 500 index.",
        REQUIRES_REALTIME_DATA_FIELD: True,
        REQUIRES_CONFIRMATION_FIELD: True,
        CONFIRMATION_GRANTED_FIELD: True,
    }

    result = gate.evaluate(
        InvestoryPolicyInput(payload=payload, supports_realtime_data=True)
    )

    assert result.action == InvestoryAction.EXECUTE_LEARNING_TASK
    assert result.reason == InvestoryPolicyReason.READY_TO_EXECUTE
    assert result.requires_realtime_data is True
    assert result.requires_user_confirmation is True
    assert result.metadata[CANDIDATE_TASK_TYPE_METADATA_KEY] == "brief"
