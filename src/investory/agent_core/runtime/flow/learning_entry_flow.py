from enum import Enum
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
    LearningEntryDecision,
    LearningEntryState,
)
from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.runtime.flow.investory_actions import InvestoryAction
from investory.agent_core.runtime.flow.investory_policy_gate import (
    CANDIDATE_TASK_TYPE_METADATA_KEY,
    InvestoryPolicyGate,
    InvestoryPolicyInput,
    InvestoryPolicyResult,
)
from investory.agent_core.runtime.request_runner import RequestRunner
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.gateway.routing import resolve_task_spec


LEARNING_ENTRY_TASK_NAME = "learning_entry"

ACTION_FIELD = "action"
MESSAGE_FIELD = "message"
MISSING_FIELDS_FIELD = "missing_fields"
SUGGESTED_LEARNING_DIRECTION_FIELD = "suggested_learning_direction"

MISSING_INPUT_MESSAGE = (
    "Please provide enough material or instrument context to continue."
)
REFUSAL_MESSAGE = (
    "I cannot continue with this request as-is, but I can help turn it into an "
    "educational learning question."
)
REFUSAL_LEARNING_DIRECTION = (
    "Ask for an explanation, summary, or learning brief based on provided "
    "material instead of a buy, sell, timing, or allocation recommendation."
)

MISSING_ROUTE = "missing"
COMPLETE_ROUTE = "complete"
ADVICE_ROUTE = "advice"


class LearningEntryNode(str, Enum):
    EVALUATE_POLICY_GATE = "evaluate_policy_gate"
    RESOLVE_TASK_SPEC = "resolve_task_spec"
    EXECUTE_TASK = "execute_task"
    BUILD_MISSING_INPUT_RESULT = "build_missing_input_result"
    BUILD_REFUSAL_RESULT = "build_refusal_result"


class LearningEntryFlow:
    def __init__(
        self,
        executor: TaskExecutor | None = None,
        policy_gate: InvestoryPolicyGate | None = None,
        *,
        supports_realtime_data: bool = False,
    ) -> None:
        self.executor = executor or TaskExecutor()
        self.policy_gate = policy_gate or InvestoryPolicyGate()
        self.supports_realtime_data = supports_realtime_data
        self.graph = self._build_graph()

    def run(
        self,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> TaskResult:
        initial_state = LearningEntryState(
            session_id=session_id or str(uuid4()),
            input_payload=payload,
        )
        final_state = LearningEntryState.model_validate(self.graph.invoke(initial_state))
        if final_state.output is None:
            raise RuntimeError("LearningEntryFlow finished without TaskResult output.")
        return final_state.output

    def _build_graph(self):
        graph = StateGraph(LearningEntryState)

        graph.add_node(
            LearningEntryNode.EVALUATE_POLICY_GATE.value,
            self.evaluate_policy_gate,
        )
        graph.add_node(
            LearningEntryNode.RESOLVE_TASK_SPEC.value,
            self.resolve_task_spec,
        )
        graph.add_node(LearningEntryNode.EXECUTE_TASK.value, self.execute_task)
        graph.add_node(
            LearningEntryNode.BUILD_MISSING_INPUT_RESULT.value,
            self.build_missing_input_result,
        )
        graph.add_node(
            LearningEntryNode.BUILD_REFUSAL_RESULT.value,
            self.build_refusal_result,
        )

        graph.add_edge(START, LearningEntryNode.EVALUATE_POLICY_GATE.value)
        graph.add_conditional_edges(
            LearningEntryNode.EVALUATE_POLICY_GATE.value,
            self.route_after_policy_gate,
            {
                MISSING_ROUTE: LearningEntryNode.BUILD_MISSING_INPUT_RESULT.value,
                ADVICE_ROUTE: LearningEntryNode.BUILD_REFUSAL_RESULT.value,
                COMPLETE_ROUTE: LearningEntryNode.RESOLVE_TASK_SPEC.value,
            },
        )
        graph.add_edge(
            LearningEntryNode.RESOLVE_TASK_SPEC.value,
            LearningEntryNode.EXECUTE_TASK.value,
        )
        graph.add_edge(LearningEntryNode.BUILD_MISSING_INPUT_RESULT.value, END)
        graph.add_edge(LearningEntryNode.BUILD_REFUSAL_RESULT.value, END)
        graph.add_edge(LearningEntryNode.EXECUTE_TASK.value, END)

        return graph.compile()

    def evaluate_policy_gate(self, state: LearningEntryState) -> dict[str, Any]:
        policy_result = self.policy_gate.evaluate(
            InvestoryPolicyInput(
                payload=state.input_payload,
                supports_realtime_data=self.supports_realtime_data,
            )
        )
        candidate_task_type = self._candidate_task_type_from_policy(policy_result)

        update: dict[str, Any] = {
            "missing_fields": policy_result.missing_fields,
            "candidate_task_type": candidate_task_type,
            "decision": self._decision_from_policy_action(policy_result.action),
        }
        return update

    def route_after_policy_gate(self, state: LearningEntryState) -> str:
        if state.decision == LearningEntryDecision.ASK_FOR_MISSING_INPUT:
            return MISSING_ROUTE
        if state.decision == LearningEntryDecision.REFUSE_AND_REDIRECT:
            return ADVICE_ROUTE
        return COMPLETE_ROUTE

    def resolve_task_spec(self, state: LearningEntryState) -> dict[str, Any]:
        if state.candidate_task_type is None:
            raise RuntimeError("Learning entry flow has no candidate task type.")

        spec = resolve_task_spec(state.candidate_task_type.value)
        return {
            "resolved_task_name": spec.name,
            "task_payload": state.input_payload,
        }

    def execute_task(self, state: LearningEntryState) -> dict[str, Any]:
        if state.resolved_task_name is None:
            raise RuntimeError("Learning entry flow has no resolved task name.")

        spec = resolve_task_spec(state.resolved_task_name)
        result = self.executor.run(spec, state.task_payload or state.input_payload)
        return {"output": result}

    def build_missing_input_result(self, state: LearningEntryState) -> dict[str, Any]:
        result = TaskResult(
            ok=True,
            task_name=LEARNING_ENTRY_TASK_NAME,
            result={
                ACTION_FIELD: LearningEntryDecision.ASK_FOR_MISSING_INPUT.value,
                MISSING_FIELDS_FIELD: state.missing_fields,
                MESSAGE_FIELD: MISSING_INPUT_MESSAGE,
            },
        )
        return {"output": result}

    def build_refusal_result(self, state: LearningEntryState) -> dict[str, Any]:
        result = TaskResult(
            ok=True,
            task_name=LEARNING_ENTRY_TASK_NAME,
            result={
                ACTION_FIELD: LearningEntryDecision.REFUSE_AND_REDIRECT.value,
                MESSAGE_FIELD: REFUSAL_MESSAGE,
                SUGGESTED_LEARNING_DIRECTION_FIELD: REFUSAL_LEARNING_DIRECTION,
            },
        )
        return {"output": result}

    @staticmethod
    def _candidate_task_type_from_policy(
        policy_result: InvestoryPolicyResult,
    ) -> LearningEntryCandidateTaskType | None:
        candidate_task_type = policy_result.metadata.get(CANDIDATE_TASK_TYPE_METADATA_KEY)
        if candidate_task_type is None:
            return None
        return LearningEntryCandidateTaskType(candidate_task_type)

    @staticmethod
    def _decision_from_policy_action(action: InvestoryAction) -> LearningEntryDecision:
        return LearningEntryDecision(action.value)


def build_learning_entry_flow(
    executor: TaskExecutor | None = None,
    runner: RequestRunner | None = None,
) -> LearningEntryFlow:
    resolved_executor = executor or TaskExecutor(runner=runner)
    return LearningEntryFlow(executor=resolved_executor)
