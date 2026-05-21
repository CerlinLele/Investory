"""Retry policy helpers for model calls."""

from investory.agent_core.contracts.result_types import extract_status_code

RETRYABLE_STATUS_CODES = {408, 409, 429}


def is_retryable_model_error(exc: Exception) -> bool:
    """Return whether a model-call failure is likely transient."""

    status_code = extract_status_code(exc)
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    if status_code is not None:
        return status_code >= 500

    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True

    exception_name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "timeout" in exception_name or "timeout" in message


def calculate_retry_delay(retry_count: int) -> float:
    """Calculate exponential backoff delay in seconds."""

    return min(0.5 * (2**retry_count), 8.0)
