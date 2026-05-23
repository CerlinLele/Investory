from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from investory.agent_core.contracts.flow_state import TaskFlowState
from investory.agent_core.contracts.result_types import TaskResult, normalize_task_error
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.message_builder import build_messages
from investory.agent_core.runtime.request_runner import (
    ModelCallError,
    RequestRunner,
    StructuredOutputError,
)


def build_execution_context(spec: TaskSpec, payload: dict[str, Any]) -> TaskFlowState:
    state = TaskFlowState(
        task_id=str(uuid4()),
        task_name=spec.name,
        input_payload=payload,
        status="running",
    )

    try:
        validated_input = spec.input_model.model_validate(payload)
    except ValidationError as exc:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(exc, stage="input_validation"),
            }
        )

    validated_payload = validated_input.model_dump()

    try:
        messages = build_messages(spec, validated_payload)
    except Exception as exc:
        return state.model_copy(
            update={
                "status": "error",
                "validated_input": validated_payload,
                "error": normalize_task_error(exc, stage="prompt_build"),
            }
        )

    return state.model_copy(
        update={
            "validated_input": validated_payload,
            "messages": messages,
        }
    )


def invoke_task_model(
    state: TaskFlowState,
    spec: TaskSpec,
    runner: RequestRunner,
) -> TaskFlowState:
    if state.messages is None:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(
                    ValueError("Task flow state has no messages."),
                    stage="prompt_build",
                ),
            }
        )

    try:
        parsed = runner.run(state.messages, spec.output_model)
    except StructuredOutputError as exc:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(
                    exc.original,
                    stage="output_validation",
                    retry_count=exc.retry_count,
                ),
            }
        )
    except ValidationError as exc:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(exc, stage="output_validation"),
            }
        )
    except ModelCallError as exc:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(
                    exc.original,
                    stage="model_call",
                    retry_count=exc.retry_count,
                ),
            }
        )
    except Exception as exc:
        return state.model_copy(
            update={
                "status": "error",
                "error": normalize_task_error(exc, stage="model_call"),
            }
        )

    return state.model_copy(update={"model_result": parsed.model_dump()})


def build_task_result(state: TaskFlowState, spec: TaskSpec) -> TaskFlowState:
    if state.error is not None:
        output = TaskResult(
            ok=False,
            task_name=spec.name,
            error=state.error,
        )
        return state.model_copy(update={"status": "error", "output": output})

    output = TaskResult(
        ok=True,
        task_name=spec.name,
        result=state.model_result,
    )
    return state.model_copy(update={"status": "done", "output": output})


class TaskExecutionPipeline:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()

    def run(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskResult:
        state = build_execution_context(spec, payload)
        if state.error is None:
            state = invoke_task_model(state, spec, self.runner)

        state = build_task_result(state, spec)
        if state.output is None:
            raise RuntimeError(
                "TaskExecutionPipeline finished without TaskResult output."
            )
        return state.output


# Backward-compatible aliases for existing imports/tests.
prepare_context = build_execution_context
call_model = invoke_task_model
finalize_result = build_task_result
MinimalTaskFlow = TaskExecutionPipeline
