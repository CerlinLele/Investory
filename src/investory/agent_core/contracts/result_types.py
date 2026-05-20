from typing import Literal

from pydantic import BaseModel


TaskErrorType = Literal[
    "input_validation_failed",
    "prompt_load_failed",
    "model_config_error",
    "provider_auth_error",
    "rate_limited",
    "provider_unavailable",
    "timeout",
    "structured_output_failed",
    "unknown_error",
]

TaskStage = Literal[
    "input_validation",
    "prompt_build",
    "model_call",
    "output_validation",
]


class TaskError(BaseModel):
    error_type: TaskErrorType
    stage: TaskStage
    user_safe_message: str
    retryable: bool = False

    request_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status_code: int | None = None
    retry_count: int = 0
    fallback_used: bool = False

    debug_message: str | None = None


class TaskResult(BaseModel):
    ok: bool
    task_name: str
    result: dict | None = None
    error: TaskError | None = None


def extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def _task_error(
    *,
    error_type: TaskErrorType,
    stage: TaskStage,
    user_safe_message: str,
    retryable: bool,
    request_id: str | None,
    provider: str | None,
    model: str | None,
    status_code: int | None,
    retry_count: int,
    fallback_used: bool,
    debug_message: str,
) -> TaskError:
    return TaskError(
        error_type=error_type,
        stage=stage,
        user_safe_message=user_safe_message,
        retryable=retryable,
        request_id=request_id,
        provider=provider,
        model=model,
        status_code=status_code,
        retry_count=retry_count,
        fallback_used=fallback_used,
        debug_message=debug_message,
    )


def normalize_task_error(
    exc: Exception,
    *,
    stage: TaskStage,
    provider: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
    retry_count: int = 0,
    fallback_used: bool = False,
) -> TaskError:
    status_code = extract_status_code(exc)
    raw_message = str(exc)
    normalized_message = raw_message.lower()
    common = {
        "stage": stage,
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "status_code": status_code,
        "retry_count": retry_count,
        "fallback_used": fallback_used,
        "debug_message": raw_message,
    }

    if stage == "input_validation":
        return _task_error(
            error_type="input_validation_failed",
            user_safe_message=(
                "The input does not match the task requirements. "
                "Please check it and try again."
            ),
            retryable=False,
            **common,
        )

    if stage == "prompt_build":
        return _task_error(
            error_type="prompt_load_failed",
            user_safe_message=(
                "The task configuration is temporarily unavailable. "
                "Please try again later."
            ),
            retryable=False,
            **common,
        )

    if stage == "output_validation":
        return _task_error(
            error_type="structured_output_failed",
            user_safe_message=(
                "The AI response did not match the required format. "
                "Please try again later."
            ),
            retryable=True,
            **common,
        )

    if status_code in {401, 403}:
        error_type: TaskErrorType = "provider_auth_error"
        user_safe_message = (
            "The AI service configuration is unavailable. "
            "Please contact the maintainer to check access permissions."
        )
        retryable = False
    elif status_code == 429:
        error_type = "rate_limited"
        user_safe_message = "The AI service is temporarily busy. Please try again later."
        retryable = True
    elif status_code is not None and status_code >= 500:
        error_type = "provider_unavailable"
        user_safe_message = (
            "The AI service is temporarily unavailable. Please try again later."
        )
        retryable = True
    elif isinstance(exc, TimeoutError) or "timeout" in normalized_message:
        error_type = "timeout"
        user_safe_message = "The AI service timed out. Please try again later."
        retryable = True
    elif isinstance(exc, (ImportError, ValueError)):
        error_type = "model_config_error"
        user_safe_message = (
            "The AI service configuration is unavailable. "
            "Please contact the maintainer to check the configuration."
        )
        retryable = False
    else:
        error_type = "unknown_error"
        user_safe_message = "The task failed to run. Please try again later."
        retryable = False

    return _task_error(
        error_type=error_type,
        user_safe_message=user_safe_message,
        retryable=retryable,
        **common,
    )
