from time import perf_counter
from typing import Any, Protocol

from pydantic import ValidationError

from investory.agent_core.contracts.action_contract import ActionCall, ActionResult
from investory.agent_core.contracts.action_decision import build_ask_missing_fields_action
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.tools import (
    ToolCallRecord,
    ToolExecutionError,
    ToolRegistry,
    UnknownToolError,
    build_mock_tool_registry,
)


class ActionExecutor(Protocol):
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        ...


class AskMissingFieldsExecutor:
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        action = build_ask_missing_fields_action(
            task_name=call.task_name,
            missing_fields=call.params["missing_fields"],
        )

        return ActionResult(
            action=call.action,
            task_name=call.task_name,
            status="requires_user_input",
            result=action.model_dump(),
            user_message=action.user_message,
        )


class RunTaskModelExecutor:
    def __init__(self, task_executor: TaskExecutor | None = None) -> None:
        self.task_executor = task_executor or TaskExecutor()

    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        task_result = self.task_executor.run(spec, call.params["payload"])
        return action_result_from_task_result(call, task_result)


class RunToolExecutor:
    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self.tool_registry = tool_registry or build_mock_tool_registry()

    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        del spec
        tool_name = str(call.params.get("tool_name", ""))
        payload = _tool_args(call.params.get("payload"))
        started_at = perf_counter()

        try:
            tool = self.tool_registry.get(tool_name)
            validated_payload = tool.input_model.model_validate(payload)
            output = tool.run(validated_payload)
            validated_output = tool.output_model.model_validate(output)
            tool_result = validated_output.model_dump()
            record = ToolCallRecord(
                tool_name=tool_name,
                args=payload,
                result=tool_result,
                elapsed_ms=_elapsed_ms(started_at),
            )
            return ActionResult(
                action=call.action,
                task_name=call.task_name,
                status="success",
                result={
                    "tool_name": tool_name,
                    "tool_result": tool_result,
                    "tool_call": record.model_dump(),
                },
            )
        except UnknownToolError as exc:
            return _failed_tool_action_result(
                call,
                tool_name=tool_name,
                payload=payload,
                started_at=started_at,
                error_message=str(exc),
                error=TaskError(
                    error_type="unknown_error",
                    stage="model_call",
                    user_safe_message=(
                        "The requested tool is unavailable. Please try again later."
                    ),
                    retryable=False,
                    debug_message=str(exc),
                ),
            )
        except ValidationError as exc:
            return _failed_tool_action_result(
                call,
                tool_name=tool_name,
                payload=payload,
                started_at=started_at,
                error_message=str(exc),
                error=TaskError(
                    error_type="input_validation_failed",
                    stage="input_validation",
                    user_safe_message=(
                        "The tool input does not match the required format. "
                        "Please check it and try again."
                    ),
                    retryable=False,
                    debug_message=str(exc),
                ),
            )
        except ToolExecutionError as exc:
            return _failed_tool_action_result(
                call,
                tool_name=tool_name,
                payload=payload,
                started_at=started_at,
                error_message=str(exc),
                error=TaskError(
                    error_type="provider_unavailable",
                    stage="model_call",
                    user_safe_message=(
                        "The tool provider is temporarily unavailable. "
                        "Please try again later."
                    ),
                    retryable=True,
                    debug_message=str(exc),
                ),
            )
        except TimeoutError as exc:
            return _failed_tool_action_result(
                call,
                tool_name=tool_name,
                payload=payload,
                started_at=started_at,
                error_message=str(exc),
                error=TaskError(
                    error_type="timeout",
                    stage="model_call",
                    user_safe_message="The tool timed out. Please try again later.",
                    retryable=True,
                    debug_message=str(exc),
                ),
            )
        except Exception as exc:
            return _failed_tool_action_result(
                call,
                tool_name=tool_name,
                payload=payload,
                started_at=started_at,
                error_message=str(exc),
                error=TaskError(
                    error_type="unknown_error",
                    stage="model_call",
                    user_safe_message="The tool failed to run. Please try again later.",
                    retryable=False,
                    debug_message=str(exc),
                ),
            )


class RefuseInvestmentAdviceExecutor:
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        refused_reason = call.params.get("refused_reason") or call.decision_reason
        allowed_alternative = call.params.get("allowed_alternative")
        user_message = call.params.get("user_message") or (
            "I cannot decide whether you should buy or sell. "
            "I can help turn this into an educational brief based on materials you provide."
        )

        return ActionResult(
            action=call.action,
            task_name=call.task_name,
            status="refused",
            result={
                "action": call.action,
                "task_name": call.task_name,
                "refused_reason": refused_reason,
                "allowed_alternative": allowed_alternative,
                "user_message": user_message,
            },
            user_message=user_message,
        )


def action_result_from_task_result(
    call: ActionCall,
    task_result: TaskResult,
) -> ActionResult:
    status = "success" if task_result.ok else "failed"
    return ActionResult(
        action=call.action,
        task_name=call.task_name,
        status=status,
        result=task_result.result,
        error=task_result.error,
    )


def _tool_args(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _failed_tool_action_result(
    call: ActionCall,
    *,
    tool_name: str,
    payload: dict[str, Any],
    started_at: float,
    error_message: str,
    error: TaskError,
) -> ActionResult:
    record = ToolCallRecord(
        tool_name=tool_name,
        args=payload,
        error=error_message,
        elapsed_ms=_elapsed_ms(started_at),
    )
    return ActionResult(
        action=call.action,
        task_name=call.task_name,
        status="failed",
        result={
            "tool_name": tool_name,
            "tool_call": record.model_dump(),
        },
        error=error,
    )
