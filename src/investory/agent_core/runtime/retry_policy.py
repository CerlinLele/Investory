"""Retry policy helpers for model calls."""

RETRYABLE_STATUS_CODES = {408, 409, 429}


def extract_status_code(exc: Exception) -> int | None:
    """Extract a provider HTTP status code from common exception shapes."""

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


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
