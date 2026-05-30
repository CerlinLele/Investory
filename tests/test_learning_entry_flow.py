import pytest

from investory.agent_core.contracts.learning_entry_state import LearningEntryDecision
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.learning_entry_flow import (
    ACTION_FIELD,
    LEARNING_ENTRY_TASK_NAME,
    MISSING_FIELDS_FIELD,
    SUGGESTED_LEARNING_DIRECTION_FIELD,
    LearningEntryFlow,
)
from investory.agent_core.runtime.flow.learning_entry_rules import (
    INSTRUMENT_NAME_OR_CODE_FIELD,
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    SOURCE_MATERIAL_FIELD,
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
