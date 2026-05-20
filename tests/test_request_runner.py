from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from investory.agent_core.runtime.request_runner import ModelCallError, RequestRunner


class AnswerResult(BaseModel):
    answer: str


class ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class FakeStructuredModel:
    def __init__(self, *outcomes: BaseModel | Exception) -> None:
        self.outcomes = list(outcomes)
        self.invoked_messages: list[Any] | None = None
        self.invoke_count = 0

    def invoke(self, messages: list[Any]) -> BaseModel:
        self.invoke_count += 1
        self.invoked_messages = messages
        if not self.outcomes:
            raise AssertionError("FakeStructuredModel requires at least one outcome.")

        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome

        return outcome


class FakeChatModel:
    def __init__(self, structured_model: FakeStructuredModel) -> None:
        self.structured_model = structured_model
        self.output_model: type[BaseModel] | None = None

    def with_structured_output(
        self,
        output_model: type[BaseModel],
    ) -> FakeStructuredModel:
        self.output_model = output_model
        return self.structured_model


def test_request_runner_invokes_model_with_structured_output():
    expected_result = AnswerResult(answer="Investory helps with investment learning.")
    structured_model = FakeStructuredModel(expected_result)
    chat_model = FakeChatModel(structured_model)
    runner = RequestRunner(model=chat_model, max_retries=2)
    messages = [HumanMessage(content="What is Investory?")]

    result = runner.run(messages, AnswerResult)

    assert result == expected_result
    assert chat_model.output_model is AnswerResult
    assert structured_model.invoked_messages == messages
    assert structured_model.invoke_count == 1


def test_request_runner_retries_retryable_error_then_returns_success():
    expected_result = AnswerResult(answer="Recovered.")
    structured_model = FakeStructuredModel(
        ProviderError("rate limited", status_code=429),
        expected_result,
    )
    chat_model = FakeChatModel(structured_model)
    delays: list[float] = []
    runner = RequestRunner(
        model=chat_model,
        max_retries=2,
        sleep_fn=delays.append,
    )
    messages = [HumanMessage(content="What is Investory?")]

    result = runner.run(messages, AnswerResult)

    assert result == expected_result
    assert structured_model.invoke_count == 2
    assert delays == [0.5]


def test_request_runner_raises_model_call_error_after_retry_limit():
    structured_model = FakeStructuredModel(
        ProviderError("upstream unavailable", status_code=503),
        ProviderError("upstream unavailable", status_code=503),
        ProviderError("upstream unavailable", status_code=503),
    )
    chat_model = FakeChatModel(structured_model)
    delays: list[float] = []
    runner = RequestRunner(
        model=chat_model,
        max_retries=2,
        sleep_fn=delays.append,
    )
    messages = [HumanMessage(content="What is Investory?")]

    with pytest.raises(ModelCallError) as exc_info:
        runner.run(messages, AnswerResult)

    assert exc_info.value.retry_count == 2
    assert exc_info.value.status_code == 503
    assert structured_model.invoke_count == 3
    assert delays == [0.5, 1.0]


def test_request_runner_does_not_retry_non_retryable_error():
    structured_model = FakeStructuredModel(
        ProviderError("unauthorized", status_code=401),
    )
    chat_model = FakeChatModel(structured_model)
    delays: list[float] = []
    runner = RequestRunner(
        model=chat_model,
        max_retries=2,
        sleep_fn=delays.append,
    )
    messages = [HumanMessage(content="What is Investory?")]

    with pytest.raises(ModelCallError) as exc_info:
        runner.run(messages, AnswerResult)

    assert exc_info.value.retry_count == 0
    assert exc_info.value.status_code == 401
    assert structured_model.invoke_count == 1
    assert delays == []


def test_request_runner_retries_timeout_then_returns_success():
    expected_result = AnswerResult(answer="Recovered after timeout.")
    structured_model = FakeStructuredModel(
        TimeoutError("request timeout"),
        expected_result,
    )
    chat_model = FakeChatModel(structured_model)
    delays: list[float] = []
    runner = RequestRunner(
        model=chat_model,
        max_retries=1,
        sleep_fn=delays.append,
    )
    messages = [HumanMessage(content="What is Investory?")]

    result = runner.run(messages, AnswerResult)

    assert result == expected_result
    assert structured_model.invoke_count == 2
    assert delays == [0.5]


def test_request_runner_reraises_validation_error_without_retry():
    try:
        AnswerResult.model_validate({})
    except ValidationError as exc:
        validation_error = exc

    structured_model = FakeStructuredModel(validation_error)
    chat_model = FakeChatModel(structured_model)
    delays: list[float] = []
    runner = RequestRunner(
        model=chat_model,
        max_retries=2,
        sleep_fn=delays.append,
    )
    messages = [HumanMessage(content="What is Investory?")]

    with pytest.raises(ValidationError):
        runner.run(messages, AnswerResult)

    assert structured_model.invoke_count == 1
    assert delays == []
