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
)
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

INVESTMENT_ADVICE_TERMS = (
    "buy",
    "sell",
    "should i invest",
    "should i buy",
    "should i sell",
    "recommend",
    "allocation",
    "position size",
    "\u4e70",
    "\u5356",
    "\u4e70\u5165",
    "\u5356\u51fa",
    "\u8be5\u4e0d\u8be5",
    "\u9002\u5408\u4e70\u5417",
    "\u80fd\u4e70\u5417",
    "\u8981\u4e0d\u8981\u4e70",
    "\u914d\u7f6e",
    "\u4ed3\u4f4d",
    "\u62e9\u65f6",
)

MISSING_ROUTE = "missing"
COMPLETE_ROUTE = "complete"
ADVICE_ROUTE = "advice"
LEARNING_ROUTE = "learning"


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

        graph.add_node("check_missing_fields", self.check_missing_fields)
        graph.add_node("decide_policy", self.decide_policy)
        graph.add_node("resolve_task_spec", self.resolve_task_spec)
        graph.add_node("execute_task", self.execute_task)
        graph.add_node("build_missing_input_result", self.build_missing_input_result)
        graph.add_node("build_refusal_result", self.build_refusal_result)

        graph.add_edge(START, "check_missing_fields")
        graph.add_conditional_edges(
            "check_missing_fields",
            self.route_after_missing_check,
            {
                MISSING_ROUTE: "build_missing_input_result",
                COMPLETE_ROUTE: "decide_policy",
            },
        )
        graph.add_conditional_edges(
            "decide_policy",
            self.route_after_policy_decision,
            {
                ADVICE_ROUTE: "build_refusal_result",
                LEARNING_ROUTE: "resolve_task_spec",
            },
        )
        graph.add_edge("resolve_task_spec", "execute_task")
        graph.add_edge("build_missing_input_result", END)
        graph.add_edge("build_refusal_result", END)
        graph.add_edge("execute_task", END)

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

        if _looks_like_investment_advice(state.input_payload):
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


def _looks_like_investment_advice(payload: dict[str, Any]) -> bool:
    text = " ".join(str(value) for value in payload.values()).lower()
    return any(term in text for term in INVESTMENT_ADVICE_TERMS)
