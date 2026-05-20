import pytest

from investory.agent_core.runtime.retry_policy import (
    calculate_retry_delay,
    extract_status_code,
    is_retryable_model_error,
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


def test_extract_status_code_from_exception_attribute():
    assert extract_status_code(ProviderError("rate limited", status_code=429)) == 429


def test_extract_status_code_from_response_attribute():
    assert extract_status_code(ResponseError("unavailable", status_code=503)) == 503


def test_extract_status_code_returns_none_when_missing():
    assert extract_status_code(Exception("unknown")) is None


@pytest.mark.parametrize("status_code", [408, 409, 429, 500, 502, 503])
def test_is_retryable_model_error_accepts_transient_status_codes(status_code: int):
    error = ProviderError("transient provider error", status_code=status_code)

    assert is_retryable_model_error(error) is True


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
def test_is_retryable_model_error_rejects_non_retryable_status_codes(status_code: int):
    error = ProviderError("non-retryable provider error", status_code=status_code)

    assert is_retryable_model_error(error) is False


def test_is_retryable_model_error_accepts_timeout_error():
    assert is_retryable_model_error(TimeoutError("request timed out")) is True


def test_is_retryable_model_error_accepts_timeout_message():
    assert is_retryable_model_error(Exception("provider timeout")) is True


def test_is_retryable_model_error_accepts_connection_error():
    assert is_retryable_model_error(ConnectionError("connection reset")) is True


def test_is_retryable_model_error_rejects_unknown_error():
    assert is_retryable_model_error(Exception("invalid model name")) is False


@pytest.mark.parametrize(
    ("retry_count", "expected_delay"),
    [
        (0, 0.5),
        (1, 1.0),
        (2, 2.0),
        (3, 4.0),
        (4, 8.0),
        (5, 8.0),
    ],
)
def test_calculate_retry_delay_uses_capped_exponential_backoff(
    retry_count: int,
    expected_delay: float,
):
    assert calculate_retry_delay(retry_count) == expected_delay
