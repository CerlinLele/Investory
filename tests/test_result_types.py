from investory.agent_core.contracts.result_types import (
    TaskError,
    TaskResult,
    normalize_task_error,
)


class ProviderError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class ResponseError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.response = Response(status_code)


def test_task_result_accepts_success_payload():
    result = TaskResult(ok=True, task_name="policy_qa", result={"answer": "yes"})

    assert result.error is None
    assert result.result == {"answer": "yes"}


def test_normalize_task_error_marks_input_validation_as_non_retryable():
    error = normalize_task_error(ValueError("missing field"), stage="input_validation")

    assert error.error_type == "input_validation_failed"
    assert error.stage == "input_validation"
    assert error.retryable is False
    assert error.user_safe_message.startswith("The input does not match")
    assert error.debug_message == "missing field"


def test_normalize_task_error_extracts_rate_limit_status_code():
    error = normalize_task_error(
        ProviderError("too many requests", status_code=429),
        stage="model_call",
        provider="openai",
        model="gpt-test",
        request_id="req_123",
        retry_count=2,
    )

    assert error.error_type == "rate_limited"
    assert error.retryable is True
    assert error.status_code == 429
    assert error.provider == "openai"
    assert error.model == "gpt-test"
    assert error.request_id == "req_123"
    assert error.retry_count == 2


def test_normalize_task_error_extracts_response_status_code():
    error = normalize_task_error(
        ResponseError("upstream unavailable", status_code=503),
        stage="model_call",
    )

    assert error.error_type == "provider_unavailable"
    assert error.retryable is True
    assert error.status_code == 503


def test_normalize_task_error_classifies_timeout_messages():
    error = normalize_task_error(Exception("request timeout"), stage="model_call")

    assert error.error_type == "timeout"
    assert error.retryable is True


def test_normalize_task_error_classifies_model_config_errors():
    error = normalize_task_error(ImportError("missing provider"), stage="model_call")

    assert error.error_type == "model_config_error"
    assert error.retryable is False


def test_task_result_accepts_error_payload():
    task_error = TaskError(
        error_type="unknown_error",
        stage="model_call",
        user_safe_message="The task failed to run. Please try again later.",
    )

    result = TaskResult(ok=False, task_name="policy_qa", error=task_error)

    assert result.result is None
    assert result.error == task_error
