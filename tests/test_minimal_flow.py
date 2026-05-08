from typing import Any

from pydantic import BaseModel, ValidationError

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime import message_builder
from investory.agent_core.runtime.minimal_flow import (
    MinimalTaskFlow,
    call_model,
    finalize_result,
    prepare_context,
)


class QuestionInput(BaseModel):
    material_text: str
    question: str


class AnswerResult(BaseModel):
    answer: str


class FakeRunner:
    def __init__(self, result: BaseModel | None = None, exc: Exception | None = None):
        self.result = result
        self.exc = exc
        self.messages: list[Any] | None = None
        self.output_model: type[BaseModel] | None = None

    def run(self, messages: list[Any], output_model: type[BaseModel]) -> BaseModel:
        self.messages = messages
        self.output_model = output_model
        if self.exc is not None:
            raise self.exc
        if self.result is None:
            raise AssertionError("FakeRunner requires result or exc.")
        return self.result


def _spec() -> TaskSpec:
    return TaskSpec(
        name="finance_qa",
        prompt_name="finance_qa",
        input_model=QuestionInput,
        output_model=AnswerResult,
    )


def _payload() -> dict[str, str]:
    return {
        "material_text": "Maximum drawdown is a peak-to-trough decline.",
        "question": "What is maximum drawdown?",
    }


def _load_prompt_text(*parts: str) -> str:
    prompts = {
        ("base", "system.md"): "You are an investment learning assistant.",
        ("base", "common_rules.md"): "Answer only from the input data.",
        (
            "base",
            "input_data_block.md",
        ): "Input data only:\n<input_json>\n{input_json}\n</input_json>",
        (
            "tasks",
            "finance_qa.md",
        ): "Rules:\n{common_rules}\n\n{input_data_block}",
    }
    return prompts[parts]


def test_minimal_task_flow_returns_success_result(monkeypatch):
    monkeypatch.setattr(message_builder, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(result=AnswerResult(answer="Maximum drawdown measures loss."))
    flow = MinimalTaskFlow(runner=runner)

    result = flow.run(_spec(), _payload())

    assert result.ok is True
    assert result.task_name == "finance_qa"
    assert result.result == {"answer": "Maximum drawdown measures loss."}
    assert result.error is None
    assert runner.output_model is AnswerResult
    assert runner.messages is not None
    assert "Maximum drawdown is a peak-to-trough decline." in runner.messages[1].content


def test_minimal_task_flow_nodes_prepare_call_and_finalize_result(monkeypatch):
    monkeypatch.setattr(message_builder, "load_prompt_text", _load_prompt_text)
    spec = _spec()
    state = prepare_context(spec, _payload())

    assert state.status == "running"
    assert state.validated_input == _payload()
    assert state.messages is not None
    assert state.error is None

    runner = FakeRunner(result=AnswerResult(answer="Maximum drawdown measures loss."))
    state = call_model(state, spec, runner)

    assert state.model_result == {"answer": "Maximum drawdown measures loss."}
    assert state.error is None

    state = finalize_result(state, spec)

    assert state.status == "done"
    assert state.output is not None
    assert state.output.ok is True
    assert state.output.result == {"answer": "Maximum drawdown measures loss."}


def test_minimal_task_flow_returns_input_validation_error(monkeypatch):
    monkeypatch.setattr(message_builder, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(result=AnswerResult(answer="unused"))
    flow = MinimalTaskFlow(runner=runner)

    result = flow.run(_spec(), {"question": "What is maximum drawdown?"})

    assert result.ok is False
    assert result.result is None
    assert result.error is not None
    assert result.error.error_type == "input_validation_failed"
    assert result.error.stage == "input_validation"
    assert runner.messages is None


def test_minimal_task_flow_returns_prompt_build_error(monkeypatch):
    def raise_prompt_error(*parts: str) -> str:
        raise FileNotFoundError("missing prompt")

    monkeypatch.setattr(message_builder, "load_prompt_text", raise_prompt_error)
    flow = MinimalTaskFlow(
        runner=FakeRunner(result=AnswerResult(answer="unused")),
    )

    result = flow.run(_spec(), _payload())

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "prompt_load_failed"
    assert result.error.stage == "prompt_build"


def test_minimal_task_flow_returns_output_validation_error(monkeypatch):
    monkeypatch.setattr(message_builder, "load_prompt_text", _load_prompt_text)
    try:
        AnswerResult.model_validate({})
    except ValidationError as exc:
        validation_error = exc
    runner = FakeRunner(exc=validation_error)
    flow = MinimalTaskFlow(runner=runner)

    result = flow.run(_spec(), _payload())

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "structured_output_failed"
    assert result.error.stage == "output_validation"


def test_minimal_task_flow_returns_model_call_error(monkeypatch):
    monkeypatch.setattr(message_builder, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(exc=TimeoutError("request timeout"))
    flow = MinimalTaskFlow(runner=runner)

    result = flow.run(_spec(), _payload())

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "timeout"
    assert result.error.stage == "model_call"
