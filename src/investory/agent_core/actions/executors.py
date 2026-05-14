from collections.abc import Callable
from typing import Protocol

from investory.agent_core.contracts.action_contract import ActionCall, ActionResult
from investory.agent_core.contracts.action_decision import build_ask_missing_fields_action
from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.tools.instrument_profile import fetch_instrument_profile


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


class FetchThenRunInstrumentBriefExecutor:
    def __init__(
        self,
        task_executor: TaskExecutor | None = None,
        fetcher: Callable[[str], ToolResult] | None = None,
    ) -> None:
        self.task_executor = task_executor or TaskExecutor()
        self.fetcher = fetcher or fetch_instrument_profile

    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        instrument_name_or_code = str(call.params["instrument_name_or_code"]).strip()
        tool_result = self.fetcher(instrument_name_or_code)

        if not tool_result.ok or not tool_result.data:
            user_message = (
                "I could not fetch public source material for this instrument. "
                "Please paste a factsheet, fund description, or research excerpt."
            )
            return ActionResult(
                action=call.action,
                task_name=call.task_name,
                status="requires_user_input",
                result={
                    "action": call.action,
                    "task_name": call.task_name,
                    "instrument_name_or_code": instrument_name_or_code,
                    "tool_error_type": tool_result.error_type,
                    "tool_error_message": tool_result.error_message,
                },
                user_message=user_message,
            )

        payload = dict(call.params["payload"])
        payload["source_material"] = tool_result.data["source_material"]
        task_result = self.task_executor.run(spec, payload)
        return action_result_from_task_result(call, task_result)


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
