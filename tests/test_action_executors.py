from pydantic import BaseModel

from investory.agent_core.actions.executors import (
    AskMissingFieldsExecutor,
    RefuseInvestmentAdviceExecutor,
    RunTaskModelExecutor,
    RunToolExecutor,
)
from investory.agent_core.contracts.action_contract import ActionCall
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK
from investory.agent_core.tools import ToolExecutionError, ToolRegistry, build_mock_tool_registry


class FakeTaskExecutor:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.calls: list[tuple[object, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec, payload))
        return self.result


class EchoToolInput(BaseModel):
    query: str


class EchoToolOutput(BaseModel):
    answer: str


class BrokenTool:
    name = "broken_tool"
    description = "Raises a tool execution error for tests."
    input_model = EchoToolInput
    output_model = EchoToolOutput

    def run(self, payload: BaseModel) -> BaseModel:
        validated_payload = self.input_model.model_validate(payload)
        if validated_payload.query == "timeout":
            raise TimeoutError("tool timed out")
        raise ToolExecutionError("provider unavailable")


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


def test_run_tool_executor_returns_successful_tool_result():
    call = ActionCall(
        action="run_tool",
        task_name="instrument_brief",
        params={
            "tool_name": "lookup_instrument_profile",
            "payload": {"instrument_name_or_code": "VOO"},
        },
        decision_reason="Need instrument profile first.",
    )

    result = RunToolExecutor(tool_registry=build_mock_tool_registry()).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "success"
    assert result.error is None
    assert result.result is not None
    assert result.result["tool_name"] == "lookup_instrument_profile"
    assert result.result["tool_result"]["resolved_name"] == "Vanguard S&P 500 ETF"
    assert result.result["tool_call"]["tool_name"] == "lookup_instrument_profile"
    assert result.result["tool_call"]["result"] == result.result["tool_result"]


def test_run_tool_executor_converges_unknown_tool_to_failed_action_result():
    call = ActionCall(
        action="run_tool",
        task_name="instrument_brief",
        params={
            "tool_name": "missing_tool",
            "payload": {"instrument_name_or_code": "VOO"},
        },
        decision_reason="Need a tool first.",
    )

    result = RunToolExecutor(tool_registry=ToolRegistry()).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_type == "unknown_error"
    assert result.result is not None
    assert result.result["tool_name"] == "missing_tool"
    assert result.result["tool_call"]["error"] == "Unknown tool: missing_tool"


def test_run_tool_executor_converges_tool_input_validation_failure():
    call = ActionCall(
        action="run_tool",
        task_name="instrument_brief",
        params={
            "tool_name": "lookup_instrument_profile",
            "payload": {},
        },
        decision_reason="Need instrument profile first.",
    )

    result = RunToolExecutor(tool_registry=build_mock_tool_registry()).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_type == "input_validation_failed"
    assert result.error.stage == "input_validation"
    assert result.result is not None
    assert result.result["tool_call"]["tool_name"] == "lookup_instrument_profile"
    assert result.result["tool_call"]["result"] is None


def test_run_tool_executor_converges_tool_execution_error():
    call = ActionCall(
        action="run_tool",
        task_name="instrument_brief",
        params={
            "tool_name": "broken_tool",
            "payload": {"query": "ETF"},
        },
        decision_reason="Need a tool first.",
    )

    result = RunToolExecutor(tool_registry=ToolRegistry([BrokenTool()])).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_type == "provider_unavailable"
    assert result.error.retryable is True
    assert result.result is not None
    assert result.result["tool_call"]["error"] == "provider unavailable"


def test_run_tool_executor_converges_timeout_error():
    call = ActionCall(
        action="run_tool",
        task_name="instrument_brief",
        params={
            "tool_name": "broken_tool",
            "payload": {"query": "timeout"},
        },
        decision_reason="Need a tool first.",
    )

    result = RunToolExecutor(tool_registry=ToolRegistry([BrokenTool()])).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_type == "timeout"
    assert result.error.retryable is True


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
