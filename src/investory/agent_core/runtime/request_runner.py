from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from investory.agent_core.runtime.model_factory import create_chat_model


class RequestRunner:
    def __init__(self, model=None) -> None:
        self.model = model or create_chat_model()

    def run(
        self,
        messages: list[BaseMessage],
        output_model: type[BaseModel],
    ) -> BaseModel:
        structured_model = self.model.with_structured_output(output_model)
        return structured_model.invoke(messages)
