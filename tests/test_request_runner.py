from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from investory.agent_core.runtime.request_runner import RequestRunner


class AnswerResult(BaseModel):
    answer: str


class FakeStructuredModel:
    def __init__(self, result: BaseModel) -> None:
        self.result = result
        self.invoked_messages: list[Any] | None = None

    def invoke(self, messages: list[Any]) -> BaseModel:
        self.invoked_messages = messages
        return self.result


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
    runner = RequestRunner(model=chat_model)
    messages = [HumanMessage(content="What is Investory?")]

    result = runner.run(messages, AnswerResult)

    assert result == expected_result
    assert chat_model.output_model is AnswerResult
    assert structured_model.invoked_messages == messages
