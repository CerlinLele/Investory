import pytest

from investory.agent_core.contracts.learning_entry_state import LearningEntryDecision
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.learning_entry_flow import (
    ACTION_FIELD,
    GENERAL_LEARNING_CLARIFICATION_MESSAGE,
    LEARNING_ENTRY_TASK_NAME,
    MISSING_INPUT_MESSAGE,
    MISSING_FIELDS_FIELD,
    SUGGESTED_LEARNING_DIRECTION_FIELD,
    LearningEntryFlow,
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
    UNKNOWN_INPUT_MISSING_FIELDS,
)
from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
    INSTRUMENT_BRIEF_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK,
)


class FakeExecutor:
    def __init__(self, result: TaskResult | None = None) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec.name, payload))
        return self.result or TaskResult(
            ok=True,
            task_name=spec.name,
            result={"handled_by": spec.name},
        )


class FakeLearningEntryRouter:
    def __init__(self, decision: LearningEntryRouteDecision) -> None:
        self.decision = decision

    def route(self, payload: dict) -> LearningEntryRouteDecision:
        return self.decision


def test_learning_entry_flow_returns_missing_input_result_for_qa_missing_material():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run({QUESTION_FIELD: "What is an ETF?"}, session_id="session-1")

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.ASK_FOR_MISSING_INPUT
    assert result.result[MISSING_FIELDS_FIELD] == [MATERIAL_TEXT_FIELD]
    assert executor.calls == []


def test_learning_entry_flow_returns_missing_input_result_for_brief_missing_source():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run({INSTRUMENT_NAME_OR_CODE_FIELD: "VOO"})

    assert result.ok is True
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.ASK_FOR_MISSING_INPUT
    assert result.result[MISSING_FIELDS_FIELD] == [SOURCE_MATERIAL_FIELD]
    assert executor.calls == []


def test_learning_entry_flow_refuses_investment_advice_without_executor_call():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run(
        {
            MATERIAL_TEXT_FIELD: "VOO tracks the S&P 500.",
            QUESTION_FIELD: "Should I buy VOO tomorrow?",
        }
    )

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.REFUSE_AND_REDIRECT
    assert SUGGESTED_LEARNING_DIRECTION_FIELD in result.result
    assert executor.calls == []


def test_learning_entry_flow_refuses_realtime_request_without_capability():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run(
        {
            MATERIAL_TEXT_FIELD: "VOO tracks the S&P 500.",
            QUESTION_FIELD: "Give me the latest price snapshot.",
            REQUIRES_REALTIME_DATA_FIELD: True,
        }
    )

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.REFUSE_AND_REDIRECT
    assert executor.calls == []


def test_learning_entry_flow_requests_confirmation_when_policy_requires_it():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run(
        {
            MATERIAL_TEXT_FIELD: "VOO tracks the S&P 500.",
            QUESTION_FIELD: "Summarize this material.",
            REQUIRES_CONFIRMATION_FIELD: True,
            CONFIRMATION_GRANTED_FIELD: False,
        }
    )

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.ASK_FOR_MISSING_INPUT
    assert result.result[MISSING_FIELDS_FIELD] == [CONFIRMATION_GRANTED_FIELD]
    assert executor.calls == []


def test_learning_entry_flow_returns_clarification_for_low_confidence_route():
    executor = FakeExecutor()
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=LearningEntryRoute.FINANCE_QA,
            confidence=0.41,
            reason="The request looks educational but the route confidence is low.",
        )
    )
    flow = LearningEntryFlow(executor=executor, llm_router=router)

    result = flow.run({"user_input": "Help me understand this ETF."})

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.ASK_FOR_MISSING_INPUT
    assert result.result[MISSING_FIELDS_FIELD] == []
    assert (
        result.result["message"]
        == GENERAL_LEARNING_CLARIFICATION_MESSAGE
    )
    assert executor.calls == []


def test_learning_entry_flow_returns_unknown_input_fallback_without_llm_router():
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run({"user_input": "Help me with this ETF content."})

    assert result.ok is True
    assert result.task_name == LEARNING_ENTRY_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == LearningEntryDecision.ASK_FOR_MISSING_INPUT
    assert result.result[MISSING_FIELDS_FIELD] == UNKNOWN_INPUT_MISSING_FIELDS
    assert result.result["message"] == MISSING_INPUT_MESSAGE
    assert executor.calls == []


@pytest.mark.parametrize(
    ("route", "expected_task_name"),
    [
        (LearningEntryRoute.FINANCE_QA, FINANCE_QA_TASK.name),
        (LearningEntryRoute.LEARNING_MATERIAL_SUMMARY, LEARNING_MATERIAL_SUMMARY_TASK.name),
        (LearningEntryRoute.INSTRUMENT_BRIEF, INSTRUMENT_BRIEF_TASK.name),
    ],
)
def test_learning_entry_flow_executes_high_confidence_llm_learning_routes(
    route,
    expected_task_name,
):
    executor = FakeExecutor()
    router = FakeLearningEntryRouter(
        LearningEntryRouteDecision(
            route=route,
            confidence=0.93,
            reason="The route is clear and should execute.",
        )
    )
    payload = {"user_input": "Handle this learning request."}
    flow = LearningEntryFlow(executor=executor, llm_router=router)

    result = flow.run(payload)

    assert result.ok is True
    assert result.task_name == expected_task_name
    assert result.result == {"handled_by": expected_task_name}
    assert executor.calls == [(expected_task_name, payload)]


@pytest.mark.parametrize(
    ("payload", "expected_task_name"),
    [
        (
            {
                MATERIAL_TEXT_FIELD: "An ETF is a basket of assets.",
                QUESTION_FIELD: "What is an ETF?",
            },
            FINANCE_QA_TASK.name,
        ),
        (
            {MATERIAL_TEXT_FIELD: "An ETF is a basket of assets."},
            LEARNING_MATERIAL_SUMMARY_TASK.name,
        ),
        (
            {
                INSTRUMENT_NAME_OR_CODE_FIELD: "VOO",
                SOURCE_MATERIAL_FIELD: "VOO tracks the S&P 500.",
            },
            INSTRUMENT_BRIEF_TASK.name,
        ),
    ],
)
def test_learning_entry_flow_executes_complete_learning_tasks(
    payload,
    expected_task_name,
):
    executor = FakeExecutor()
    flow = LearningEntryFlow(executor=executor)

    result = flow.run(payload)

    assert result.ok is True
    assert result.task_name == expected_task_name
    assert result.result == {"handled_by": expected_task_name}
    assert executor.calls == [(expected_task_name, payload)]


def test_learning_entry_flow_preserves_downstream_executor_error_result():
    error_result = TaskResult(
        ok=False,
        task_name=FINANCE_QA_TASK.name,
        error=TaskError(
            error_type="input_validation_failed",
            stage="input_validation",
            user_safe_message="The input does not match the task requirements.",
        ),
    )
    executor = FakeExecutor(result=error_result)
    flow = LearningEntryFlow(executor=executor)

    result = flow.run(
        {
            MATERIAL_TEXT_FIELD: "An ETF is a basket of assets.",
            QUESTION_FIELD: "What is an ETF?",
        }
    )

    assert result is error_result
    assert executor.calls == [
        (
            FINANCE_QA_TASK.name,
            {
                MATERIAL_TEXT_FIELD: "An ETF is a basket of assets.",
                QUESTION_FIELD: "What is an ETF?",
            },
        )
    ]
