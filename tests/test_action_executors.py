from investory.agent_core.actions.executors import (
    AskMissingFieldsExecutor,
    RefuseInvestmentAdviceExecutor,
    RunTaskModelExecutor,
)
from investory.agent_core.contracts.action_contract import ActionCall
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK


class FakeTaskExecutor:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.calls: list[tuple[object, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec, payload))
        return self.result


def test_ask_missing_fields_executor_returns_requires_user_input_result():
    call = ActionCall(
        action="ask_missing_fields",
        task_name="instrument_brief",
        params={"missing_fields": ["source_material"]},
        decision_reason="The request is missing source_material.",
    )

    result = AskMissingFieldsExecutor().execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.action == "ask_missing_fields"
    assert result.task_name == "instrument_brief"
    assert result.status == "requires_user_input"
    assert result.result is not None
    assert result.result["action"] == "ask_missing_fields"
    assert result.result["missing_fields"] == ["source_material"]
    assert result.user_message == result.result["user_message"]


def test_run_task_model_executor_converts_successful_task_result():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }
    task_result = TaskResult(
        ok=True,
        task_name="instrument_brief",
        result={"overview": "Broad US equities."},
    )
    task_executor = FakeTaskExecutor(task_result)
    call = ActionCall(
        action="run_task_model",
        task_name="instrument_brief",
        params={"payload": payload},
        decision_reason="Ready to run.",
    )

    result = RunTaskModelExecutor(task_executor=task_executor).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "success"
    assert result.result == {"overview": "Broad US equities."}
    assert result.error is None
    assert task_executor.calls == [(INSTRUMENT_BRIEF_TASK, payload)]


def test_run_task_model_executor_converts_failed_task_result():
    task_error = TaskError(
        error_type="structured_output_failed",
        stage="output_validation",
        user_safe_message="The AI response did not match the required format.",
        retryable=True,
    )
    task_result = TaskResult(
        ok=False,
        task_name="instrument_brief",
        error=task_error,
    )
    call = ActionCall(
        action="run_task_model",
        task_name="instrument_brief",
        params={"payload": {}},
        decision_reason="Ready to run.",
    )

    result = RunTaskModelExecutor(
        task_executor=FakeTaskExecutor(task_result),
    ).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "failed"
    assert result.result is None
    assert result.error == task_error


def test_refuse_investment_advice_executor_returns_refused_result():
    call = ActionCall(
        action="refuse_investment_advice",
        task_name="instrument_brief",
        params={
            "refused_reason": "The request asks for a buy or sell decision.",
            "allowed_alternative": "I can help create an educational brief.",
            "user_message": "I cannot decide whether you should buy or sell.",
        },
        decision_reason="High-risk investment advice request.",
    )

    result = RefuseInvestmentAdviceExecutor().execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "refused"
    assert result.user_message == "I cannot decide whether you should buy or sell."
    assert result.result == {
        "action": "refuse_investment_advice",
        "task_name": "instrument_brief",
        "refused_reason": "The request asks for a buy or sell decision.",
        "allowed_alternative": "I can help create an educational brief.",
        "user_message": "I cannot decide whether you should buy or sell.",
    }
