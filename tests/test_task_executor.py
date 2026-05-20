from typing import Any

from pydantic import BaseModel, ValidationError

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime import task_executor
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.runtime.request_runner import ModelCallError


class QuestionInput(BaseModel):
    material_text: str
    question: str


class AnswerResult(BaseModel):
    answer: str


class ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


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


def test_task_executor_returns_success_result(monkeypatch):
    monkeypatch.setattr(task_executor, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(result=AnswerResult(answer="Maximum drawdown measures loss."))
    executor = TaskExecutor(runner=runner)

    result = executor.run(
        _spec(),
        {
            "material_text": "Maximum drawdown is a peak-to-trough decline.",
            "question": "What is maximum drawdown?",
        },
    )

    assert result.ok is True
    assert result.task_name == "finance_qa"
    assert result.result == {"answer": "Maximum drawdown measures loss."}
    assert result.error is None
    assert runner.output_model is AnswerResult
    assert runner.messages is not None
    assert "Maximum drawdown is a peak-to-trough decline." in runner.messages[1].content


def test_task_executor_returns_input_validation_error(monkeypatch):
    monkeypatch.setattr(task_executor, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(result=AnswerResult(answer="unused"))
    executor = TaskExecutor(runner=runner)

    result = executor.run(_spec(), {"question": "What is maximum drawdown?"})

    assert result.ok is False
    assert result.result is None
    assert result.error is not None
    assert result.error.error_type == "input_validation_failed"
    assert result.error.stage == "input_validation"
    assert runner.messages is None


def test_task_executor_returns_prompt_build_error(monkeypatch):
    def raise_prompt_error(*parts: str) -> str:
        raise FileNotFoundError("missing prompt")

    monkeypatch.setattr(task_executor, "load_prompt_text", raise_prompt_error)
    executor = TaskExecutor(runner=FakeRunner(result=AnswerResult(answer="unused")))

    result = executor.run(
        _spec(),
        {
            "material_text": "Maximum drawdown is a peak-to-trough decline.",
            "question": "What is maximum drawdown?",
        },
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "prompt_load_failed"
    assert result.error.stage == "prompt_build"


def test_task_executor_returns_output_validation_error(monkeypatch):
    monkeypatch.setattr(task_executor, "load_prompt_text", _load_prompt_text)
    try:
        AnswerResult.model_validate({})
    except ValidationError as exc:
        validation_error = exc
    runner = FakeRunner(exc=validation_error)
    executor = TaskExecutor(runner=runner)

    result = executor.run(
        _spec(),
        {
            "material_text": "Maximum drawdown is a peak-to-trough decline.",
            "question": "What is maximum drawdown?",
        },
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "structured_output_failed"
    assert result.error.stage == "output_validation"


def test_task_executor_returns_model_call_error(monkeypatch):
    monkeypatch.setattr(task_executor, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(exc=TimeoutError("request timeout"))
    executor = TaskExecutor(runner=runner)

    result = executor.run(
        _spec(),
        {
            "material_text": "Maximum drawdown is a peak-to-trough decline.",
            "question": "What is maximum drawdown?",
        },
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "timeout"
    assert result.error.stage == "model_call"


def test_task_executor_preserves_model_call_retry_count(monkeypatch):
    monkeypatch.setattr(task_executor, "load_prompt_text", _load_prompt_text)
    runner = FakeRunner(
        exc=ModelCallError(
            ProviderError("too many requests", status_code=429),
            retry_count=2,
        ),
    )
    executor = TaskExecutor(runner=runner)

    result = executor.run(
        _spec(),
        {
            "material_text": "Maximum drawdown is a peak-to-trough decline.",
            "question": "What is maximum drawdown?",
        },
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "rate_limited"
    assert result.error.stage == "model_call"
    assert result.error.retryable is True
    assert result.error.status_code == 429
    assert result.error.retry_count == 2
