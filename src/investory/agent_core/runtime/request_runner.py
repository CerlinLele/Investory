from collections.abc import Callable
from time import sleep

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ValidationError

from investory.agent_core.runtime.model_factory import create_chat_model
from investory.agent_core.runtime.retry_policy import (
    calculate_retry_delay,
    extract_status_code,
    is_retryable_model_error,
)
from investory.config import load_config


class ModelCallError(Exception):
    def __init__(self, original: Exception, retry_count: int) -> None:
        super().__init__(str(original))
        self.original = original
        self.retry_count = retry_count
        self.status_code = extract_status_code(original)
        self.response = getattr(original, "response", None)


class StructuredOutputError(Exception):
    def __init__(self, original: ValidationError, retry_count: int) -> None:
        super().__init__(str(original))
        self.original = original
        self.retry_count = retry_count


class RequestRunner:
    def __init__(
        self,
        model=None,
        max_retries: int | None = None,
        structured_output_max_retries: int = 1,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        config = load_config()
        self.model = model or create_chat_model(config)
        self.max_retries = config.llm_max_retries if max_retries is None else max_retries
        self.structured_output_max_retries = structured_output_max_retries
        self.sleep_fn = sleep_fn

    def run(
        self,
        messages: list[BaseMessage],
        output_model: type[BaseModel],
    ) -> BaseModel:
        structured_model = self.model.with_structured_output(output_model)
        model_retry_count = 0
        structured_output_retry_count = 0

        while True:
            try:
                return structured_model.invoke(messages)
            except ValidationError as exc:
                if structured_output_retry_count >= self.structured_output_max_retries:
                    raise StructuredOutputError(
                        exc,
                        structured_output_retry_count,
                    ) from exc

                structured_output_retry_count += 1
            except Exception as exc:
                if model_retry_count >= self.max_retries:
                    raise ModelCallError(exc, model_retry_count) from exc

                if not is_retryable_model_error(exc):
                    raise ModelCallError(exc, model_retry_count) from exc

                self.sleep_fn(calculate_retry_delay(model_retry_count))
                model_retry_count += 1
