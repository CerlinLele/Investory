import pytest

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)
from investory.agent_core.runtime.flow.investory_actions import InvestoryAction
from investory.agent_core.runtime.flow.investory_policy_gate import (
    CANDIDATE_TASK_TYPE_METADATA_KEY,
    DEFAULT_ROUTE_CONFIDENCE_THRESHOLD,
    InvestoryPolicyGate,
    InvestoryPolicyInput,
    InvestoryPolicyReason,
    ROUTE_CONFIDENCE_METADATA_KEY,
    ROUTE_METADATA_KEY,
    ROUTE_REASON_METADATA_KEY,
)
from investory.agent_core.runtime.flow.learning_entry_router import (
    LearningEntryRoute,
    LearningEntryRouteDecision,
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


class FakeLearningEntryRouter:
    def __init__(self, decision: LearningEntryRouteDecision) -> None:
        self.decision = decision
        self.payloads: list[dict] = []

    def route(self, payload: dict) -> LearningEntryRouteDecision:
        self.payloads.append(payload)
        return self.decision


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


def test_policy_gate_does_not_call_llm_router_when_rule_routing_succeeds() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.FINANCE_QA,
            confidence=0.9,
            reason="unused",
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {MATERIAL_TEXT_FIELD: "An ETF is a basket of assets."}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.EXECUTE_LEARNING_TASK
    assert result.metadata[CANDIDATE_TASK_TYPE_METADATA_KEY] == "summary"
    assert router.payloads == []


def test_policy_gate_calls_llm_router_only_when_rule_routing_is_unresolved() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.FINANCE_QA,
            confidence=0.86,
            reason="The user asks an educational finance question.",
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {"user_input": "Explain ETF fees using the material I pasted above."}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.EXECUTE_LEARNING_TASK
    assert result.reason == InvestoryPolicyReason.READY_TO_EXECUTE
    assert result.metadata[CANDIDATE_TASK_TYPE_METADATA_KEY] == "qa"
    assert result.metadata[ROUTE_METADATA_KEY] == "finance_qa"
    assert result.metadata[ROUTE_CONFIDENCE_METADATA_KEY] == 0.86
    assert result.metadata[ROUTE_REASON_METADATA_KEY] == (
        "The user asks an educational finance question."
    )
    assert router.payloads == [payload]


def test_policy_gate_falls_back_when_llm_route_confidence_is_low() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.FINANCE_QA,
            confidence=0.42,
            reason="The request looks educational but the task match is uncertain.",
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {"user_input": "Help me with this ETF content."}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.ASK_FOR_MISSING_INPUT
    assert result.reason == InvestoryPolicyReason.LOW_CONFIDENCE_ROUTE
    assert result.missing_fields == []
    assert result.metadata[ROUTE_METADATA_KEY] == "finance_qa"
    assert result.metadata[ROUTE_CONFIDENCE_METADATA_KEY] < (
        DEFAULT_ROUTE_CONFIDENCE_THRESHOLD
    )


def test_policy_gate_falls_back_for_general_learning_clarification_route() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.GENERAL_LEARNING_CLARIFICATION,
            confidence=0.74,
            reason="The request is educational but too ambiguous to pick one task.",
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {"user_input": "Can you help me learn from this?"}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.ASK_FOR_MISSING_INPUT
    assert result.reason == InvestoryPolicyReason.LOW_CONFIDENCE_ROUTE
    assert result.missing_fields == []
    assert result.metadata[ROUTE_METADATA_KEY] == "general_learning_clarification"


def test_policy_gate_maps_llm_missing_route_to_missing_input_result() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.ASK_FOR_MISSING_INPUT,
            confidence=0.77,
            reason="The request mentions a brief but lacks source material.",
            missing_fields=[SOURCE_MATERIAL_FIELD],
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {"user_input": "Write a brief for VOO."}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.ASK_FOR_MISSING_INPUT
    assert result.reason == InvestoryPolicyReason.MISSING_REQUIRED_INPUT
    assert result.missing_fields == [SOURCE_MATERIAL_FIELD]
    assert result.metadata[ROUTE_METADATA_KEY] == "ask_for_missing_input"


def test_policy_gate_maps_llm_refusal_route_to_refusal_result() -> None:
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.REFUSE_AND_REDIRECT,
            confidence=0.92,
            reason="The request asks whether to buy.",
        )
    )
    gate = InvestoryPolicyGate(llm_router=router)
    payload = {"user_input": "Is now a good entry point for VOO?"}

    result = gate.evaluate(InvestoryPolicyInput(payload=payload))

    assert result.action == InvestoryAction.REFUSE_AND_REDIRECT
    assert result.reason == InvestoryPolicyReason.INVESTMENT_ADVICE_REQUEST
    assert result.metadata[ROUTE_METADATA_KEY] == "refuse_and_redirect"


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
