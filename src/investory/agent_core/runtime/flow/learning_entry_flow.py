from enum import Enum
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryDecision,
    LearningEntryState,
)
from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.runtime.flow.learning_entry_decision import (
    LearningEntryPolicyDecision,
)
from investory.agent_core.runtime.flow.learning_entry_rules import (
    INSTRUMENT_NAME_OR_CODE_FIELD,
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    SOURCE_MATERIAL_FIELD,
    detect_missing_fields,
    infer_candidate_task_type,
    looks_like_investment_advice,
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
    "I cannot provide direct investment advice, but I can help turn this into "
    "a learning question."
)
REFUSAL_LEARNING_DIRECTION = (
    "Ask for an explanation, summary, or learning brief based on provided "
    "material instead of a buy, sell, timing, or allocation recommendation."
)

UNKNOWN_INPUT_MISSING_FIELDS = [
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    INSTRUMENT_NAME_OR_CODE_FIELD,
    SOURCE_MATERIAL_FIELD,
]

MISSING_ROUTE = "missing"
COMPLETE_ROUTE = "complete"
ADVICE_ROUTE = "advice"
LEARNING_ROUTE = "learning"


class LearningEntryNode(str, Enum):
    CHECK_MISSING_FIELDS = "check_missing_fields"
    DECIDE_POLICY = "decide_policy"
    RESOLVE_TASK_SPEC = "resolve_task_spec"
    EXECUTE_TASK = "execute_task"
    BUILD_MISSING_INPUT_RESULT = "build_missing_input_result"
    BUILD_REFUSAL_RESULT = "build_refusal_result"


class LearningEntryFlow:
    def __init__(self, executor: TaskExecutor | None = None) -> None:
        self.executor = executor or TaskExecutor()
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
            LearningEntryNode.CHECK_MISSING_FIELDS.value,
            self.check_missing_fields,
        )
        graph.add_node(LearningEntryNode.DECIDE_POLICY.value, self.decide_policy)
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

        graph.add_edge(START, LearningEntryNode.CHECK_MISSING_FIELDS.value)
        graph.add_conditional_edges(
            LearningEntryNode.CHECK_MISSING_FIELDS.value,
            self.route_after_missing_check,
            {
                MISSING_ROUTE: LearningEntryNode.BUILD_MISSING_INPUT_RESULT.value,
                COMPLETE_ROUTE: LearningEntryNode.DECIDE_POLICY.value,
            },
        )
        graph.add_conditional_edges(
            LearningEntryNode.DECIDE_POLICY.value,
            self.route_after_policy_decision,
            {
                ADVICE_ROUTE: LearningEntryNode.BUILD_REFUSAL_RESULT.value,
                LEARNING_ROUTE: LearningEntryNode.RESOLVE_TASK_SPEC.value,
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

    def check_missing_fields(self, state: LearningEntryState) -> dict[str, Any]:
        missing_fields = detect_missing_fields(state.input_payload)
        candidate_task_type = infer_candidate_task_type(state.input_payload)

        if candidate_task_type is None and not missing_fields:
            missing_fields = UNKNOWN_INPUT_MISSING_FIELDS

        update: dict[str, Any] = {
            "missing_fields": missing_fields,
            "candidate_task_type": candidate_task_type,
        }
        if missing_fields:
            update["decision"] = LearningEntryDecision.ASK_FOR_MISSING_INPUT
        return update

    def route_after_missing_check(self, state: LearningEntryState) -> str:
        if state.decision == LearningEntryDecision.ASK_FOR_MISSING_INPUT:
            return MISSING_ROUTE
        return COMPLETE_ROUTE

    def decide_policy(self, state: LearningEntryState) -> dict[str, Any]:
        route_action = LearningEntryDecision.EXECUTE_LEARNING_TASK
        reason = "The request can continue as an educational learning task."

        if looks_like_investment_advice(state.input_payload):
            route_action = LearningEntryDecision.REFUSE_AND_REDIRECT
            reason = "The request appears to ask for direct investment advice."

        decision = LearningEntryPolicyDecision(
            route_action=route_action,
            reason=reason,
        )
        return {"decision": decision.route_action}

    def route_after_policy_decision(self, state: LearningEntryState) -> str:
        if state.decision == LearningEntryDecision.REFUSE_AND_REDIRECT:
            return ADVICE_ROUTE
        return LEARNING_ROUTE

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


def build_learning_entry_flow(
    executor: TaskExecutor | None = None,
    runner: RequestRunner | None = None,
) -> LearningEntryFlow:
    resolved_executor = executor or TaskExecutor(runner=runner)
    return LearningEntryFlow(executor=resolved_executor)
