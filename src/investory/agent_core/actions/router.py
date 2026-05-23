from collections.abc import Mapping

from investory.agent_core.actions.executors import (
    ActionExecutor,
    AskMissingFieldsExecutor,
    RefuseInvestmentAdviceExecutor,
    RunTaskModelExecutor,
)
from investory.agent_core.contracts.action_contract import (
    ASK_MISSING_FIELDS,
    REFUSE_INVESTMENT_ADVICE,
    RUN_TASK_MODEL,
    ActionCall,
    ActionName,
)
from investory.agent_core.runtime.task_executor import TaskExecutor


class ActionRoutingError(ValueError):
    """Raised when an action call cannot be routed to an executor."""


class ActionRouter:
    def __init__(
        self,
        executors: Mapping[ActionName, ActionExecutor] | None = None,
        *,
        task_executor: TaskExecutor | None = None,
    ) -> None:
        self._executors = dict(executors or _default_executors(task_executor))

    def route(self, call: ActionCall) -> ActionExecutor:
        executor = self._executors.get(call.action)
        if executor is None:
            raise ActionRoutingError(f"No executor registered for action: {call.action}")
        return executor


def _default_executors(
    task_executor: TaskExecutor | None = None,
) -> dict[ActionName, ActionExecutor]:
    return {
        ASK_MISSING_FIELDS: AskMissingFieldsExecutor(),
        RUN_TASK_MODEL: RunTaskModelExecutor(task_executor=task_executor),
        REFUSE_INVESTMENT_ADVICE: RefuseInvestmentAdviceExecutor(),
    }


def route_action(call: ActionCall, router: ActionRouter | None = None) -> ActionExecutor:
    resolved_router = router or ActionRouter()
    return resolved_router.route(call)
