"""HTTP routes for the Investory gateway."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.learning_entry_flow import (
    LearningEntryFlow,
    build_learning_entry_flow,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.gateway.routing import UnknownTaskTypeError, resolve_task_spec
from investory.gateway.schemas import (
    HealthResponse,
    LearningEntryRequest,
    TaskErrorResponse,
    TaskRequest,
    TaskResponse,
)
from investory.gateway.session import resolve_session_id


LEARNING_ENTRY_FLOW_STATE_ATTR = "learning_entry_flow"
LEARNING_ENTRY_ROUTE = "/learning-entry"

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
    resolved_executor = executor or TaskExecutor()
    result = resolved_executor.run(spec, task_request.payload)
    return _to_gateway_response(result, session_id=session_id)


def execute_learning_entry_request(
    learning_request: LearningEntryRequest,
    *,
    flow: LearningEntryFlow | None = None,
) -> TaskResponse:
    session_id = resolve_session_id(learning_request.session_id)
    resolved_flow = flow or build_learning_entry_flow()
    result = resolved_flow.run(learning_request.payload, session_id=session_id)
    return _to_gateway_response(result, session_id=session_id)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    config = request.app.state.config

    return HealthResponse(
        ok=True,
        app_name=config.app_name,
        app_env=config.app_env,
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
    executor = getattr(request.app.state, "task_executor", None) or TaskExecutor()

    try:
        return execute_task_request(task_request, executor=executor)
    except UnknownTaskTypeError as exc:
        session_id = resolve_session_id(task_request.session_id)
        return _unknown_task_response(exc, session_id=session_id)


@router.post(LEARNING_ENTRY_ROUTE, response_model=TaskResponse)
def run_learning_entry(
    request: Request,
    learning_request: LearningEntryRequest,
) -> TaskResponse | JSONResponse:
    flow = getattr(request.app.state, LEARNING_ENTRY_FLOW_STATE_ATTR, None)

    try:
        return execute_learning_entry_request(learning_request, flow=flow)
    except UnknownTaskTypeError as exc:
        session_id = resolve_session_id(learning_request.session_id)
        return _unknown_task_response(exc, session_id=session_id)
