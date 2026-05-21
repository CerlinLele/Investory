from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from investory.agent_core.actions.router import ActionRouter
from investory.agent_core.actions.validator import validate_decision
from investory.agent_core.contracts.action_contract import (
    ActionCall,
    ActionResult,
    TaskDecision,
)
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.decision_planner import DecisionPlanner
from investory.agent_core.runtime.task_executor import TaskExecutor


class LearningQaFlowState(BaseModel):
    task_id: str
    task_name: str
    input_payload: dict[str, Any]
    decision: TaskDecision | None = None
    action_call: ActionCall | None = None
    action_result: ActionResult | None = None
    output: TaskResult | None = None
    error: TaskError | None = None


# Backward-compatible alias during naming migration.
DecisionFlowState = LearningQaFlowState


class DecisionFlow:
    def __init__(
        self,
        *,
        planner: DecisionPlanner | None = None,
        router: ActionRouter | None = None,
        task_executor: TaskExecutor | None = None,
    ) -> None:
        self.planner = planner or DecisionPlanner()
        self.router = router or ActionRouter(task_executor=task_executor)
        self.last_state: LearningQaFlowState | None = None

    def run(
        self,
        spec: TaskSpec,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> TaskResult:
        state = LearningQaFlowState(
            task_id=request_id or f"decision_{uuid4().hex}",
            task_name=spec.name,
            input_payload=dict(payload),
        )
        self.last_state = state

        decision = self.planner.decide(spec, payload)
        state.decision = decision

        action_call = validate_decision(decision, spec, request_id=request_id)
        state.action_call = action_call

        executor = self.router.route(action_call)
        action_result = executor.execute(action_call, spec)
        state.action_result = action_result

        output = backfill_action_result(action_result)
        state.output = output
        state.error = output.error
        return output


def backfill_action_result(action_result: ActionResult) -> TaskResult:
    if action_result.status == "failed":
        return TaskResult(
            ok=False,
            task_name=action_result.task_name,
            result=action_result.result,
            error=action_result.error or _missing_action_error(action_result),
        )

    return TaskResult(
        ok=True,
        task_name=action_result.task_name,
        result=action_result.result,
    )


def _missing_action_error(action_result: ActionResult) -> TaskError:
    return TaskError(
        error_type="unknown_error",
        stage="model_call",
        user_safe_message="The action failed to run. Please try again later.",
        retryable=False,
        debug_message=(
            f"Action {action_result.action!r} failed without providing a TaskError."
        ),
    )
