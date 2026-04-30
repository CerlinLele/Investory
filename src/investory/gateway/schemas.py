"""Public request and response models for the HTTP gateway."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    app_name: NonEmptyString
    app_env: NonEmptyString


class TaskRequest(BaseModel):
    """Public task execution request.

    This schema intentionally accepts a generic payload so the HTTP layer stays
    decoupled from agent_core task-specific input models.
    """

    model_config = ConfigDict(extra="forbid")

    task_type: NonEmptyString
    payload: dict[str, Any]
    session_id: NonEmptyString | None = None


class TaskErrorResponse(BaseModel):
    """Public task error shape returned by the gateway."""

    model_config = ConfigDict(extra="forbid")

    error_type: NonEmptyString
    stage: NonEmptyString
    user_safe_message: NonEmptyString
    retryable: bool = False
    request_id: NonEmptyString | None = None


class TaskResponse(BaseModel):
    """Public task execution response.

    The response mirrors the stable parts of TaskResult while adding gateway
    metadata such as session_id.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    task_name: NonEmptyString | None = None
    session_id: NonEmptyString
    result: dict[str, Any] | None = None
    error: TaskErrorResponse | None = None


__all__ = [
    "HealthResponse",
    "TaskErrorResponse",
    "TaskRequest",
    "TaskResponse",
]
