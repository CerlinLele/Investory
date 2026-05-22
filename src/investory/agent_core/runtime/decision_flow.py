from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
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
    spec: TaskSpec
    task_name: str
    input_payload: dict[str, Any]
    request_id: str | None = None
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
        self.graph = self._build_graph()
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
            spec=spec,
            task_name=spec.name,
            input_payload=dict(payload),
            request_id=request_id,
        )
        final_state = self.graph.invoke(state)
        self.last_state = LearningQaFlowState.model_validate(final_state)
        if self.last_state.output is None:
            raise RuntimeError("Flow completed without output.")
        return self.last_state.output

    def _build_graph(self):
        graph = StateGraph(LearningQaFlowState)
        graph.add_node("classify_request", self._node_classify_request)
        graph.add_node(
            "validate_decision_contract",
            self._node_validate_decision_contract,
        )
        graph.add_node("execute_routed_action", self._node_execute_routed_action)
        graph.add_node("build_task_response", self._node_build_task_response)
        graph.add_edge(START, "classify_request")
        graph.add_edge("classify_request", "validate_decision_contract")
        graph.add_edge("validate_decision_contract", "execute_routed_action")
        graph.add_edge("execute_routed_action", "build_task_response")
        graph.add_edge("build_task_response", END)
        return graph.compile()

    def classify_request(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
        payload: dict[str, Any],
    ) -> None:
        state.decision = self.planner.decide(spec, payload)

    def validate_decision_contract(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
        *,
        request_id: str | None = None,
    ) -> None:
        state.action_call = validate_decision(
            state.decision,
            spec,
            request_id=request_id,
        )

    def execute_routed_action(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
    ) -> None:
        executor = self.router.route(state.action_call)
        state.action_result = executor.execute(state.action_call, spec)

    def build_task_response(self, state: LearningQaFlowState) -> TaskResult:
        output = backfill_action_result(state.action_result)
        state.output = output
        state.error = output.error
        return output

    def _node_classify_request(self, state: LearningQaFlowState) -> dict[str, Any]:
        self.classify_request(state, state.spec, state.input_payload)
        return {"decision": state.decision}

    def _node_validate_decision_contract(
        self,
        state: LearningQaFlowState,
    ) -> dict[str, Any]:
        self.validate_decision_contract(
            state,
            state.spec,
            request_id=state.request_id,
        )
        return {"action_call": state.action_call}

    def _node_execute_routed_action(
        self,
        state: LearningQaFlowState,
    ) -> dict[str, Any]:
        self.execute_routed_action(state, state.spec)
        return {"action_result": state.action_result}

    def _node_build_task_response(self, state: LearningQaFlowState) -> dict[str, Any]:
        self.build_task_response(state)
        return {
            "output": state.output,
            "error": state.error,
        }


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
