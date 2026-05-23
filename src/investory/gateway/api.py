"""HTTP routes for the Investory gateway."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

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


@router.post("/tasks", response_model=TaskResponse)
def run_task(task_request: TaskRequest, request: Request) -> TaskResponse:
    try:
        return execute_task_request(
            task_request,
            executor=getattr(request.app.state, "task_executor", None),
        )
    except UnknownTaskTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
