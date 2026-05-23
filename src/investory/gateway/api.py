"""HTTP routes for the Investory gateway."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.learning_qa_orchestration_flow import (
    LearningQaOrchestrationFlow,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.gateway.routing import UnknownTaskTypeError, resolve_task_spec
from investory.gateway.schemas import (
    HealthResponse,
    TaskErrorResponse,
    TaskRequest,
    TaskResponse,
)
from investory.gateway.session import resolve_session_id


router = APIRouter()


def _to_gateway_error(error: TaskError) -> TaskErrorResponse:
    return TaskErrorResponse(
        error_type=error.error_type,
        stage=error.stage,
        user_safe_message=error.user_safe_message,
        retryable=error.retryable,
        request_id=error.request_id,
    )


def _to_gateway_response(result: TaskResult, *, session_id: str) -> TaskResponse:
    return TaskResponse(
        ok=result.ok,
        task_name=result.task_name,
        session_id=session_id,
        result=result.result,
        error=_to_gateway_error(result.error) if result.error is not None else None,
    )


def execute_task_request(
    task_request: TaskRequest,
    *,
    executor: TaskExecutor | None = None,
) -> TaskResponse:
    session_id = resolve_session_id(task_request.session_id)
    spec = resolve_task_spec(task_request.task_type)

    flow = LearningQaOrchestrationFlow(task_executor=executor)
    result = flow.run(spec, task_request.payload)
    return _to_gateway_response(result, session_id=session_id)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    config = request.app.state.config

    return HealthResponse(
        ok=True,
        app_name=config.app_name,
        app_env=config.app_env,
    )


def _to_task_error_response(result: TaskResult) -> TaskErrorResponse | None:
    if result.error is None:
        return None

    return TaskErrorResponse(
        error_type=result.error.error_type,
        stage=result.error.stage,
        user_safe_message=result.error.user_safe_message,
        retryable=result.error.retryable,
        request_id=result.error.request_id,
    )


def _to_task_response(result: TaskResult, *, session_id: str) -> TaskResponse:
    return TaskResponse(
        ok=result.ok,
        task_name=result.task_name,
        session_id=session_id,
        result=result.result,
        error=_to_task_error_response(result),
    )


def _unknown_task_response(
    exc: UnknownTaskTypeError,
    *,
    session_id: str,
) -> JSONResponse:
    response = TaskResponse(
        ok=False,
        task_name=None,
        session_id=session_id,
        result=None,
        error=TaskErrorResponse(
            error_type="input_validation_failed",
            stage="input_validation",
            user_safe_message=str(exc),
            retryable=False,
        ),
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(),
    )


@router.post("/tasks", response_model=TaskResponse)
def run_task(request: Request, task_request: TaskRequest) -> TaskResponse | JSONResponse:
    session_id = resolve_session_id(task_request.session_id)

    try:
        task_spec = resolve_task_spec(task_request.task_type)
    except UnknownTaskTypeError as exc:
        return _unknown_task_response(exc, session_id=session_id)

    try:
        executor = getattr(request.app.state, "task_executor", None) or TaskExecutor()
        result = executor.run(task_spec, task_request.payload)
    except Exception as exc:
        result = TaskResult(
            ok=False,
            task_name=task_spec.name,
            error=normalize_task_error(exc, stage="model_call"),
        )

    return _to_task_response(result, session_id=session_id)
