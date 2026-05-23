from typing import Any, Final
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from investory.agent_core.actions.router import ActionRouter, ActionRoutingError
from investory.agent_core.actions.validator import (
    ActionValidationError,
    validate_action_params,
    validate_decision_contract,
)
from investory.agent_core.contracts.action_contract import (
    ASK_MISSING_FIELDS,
    REFUSE_INVESTMENT_ADVICE,
    RUN_TASK_MODEL,
    ActionCall,
    ActionResult,
    TaskDecision,
)
from investory.agent_core.contracts.result_types import (
    TaskError,
    TaskResult,
    normalize_task_error,
)
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.flow.learning_qa_decision_planner import (
    LearningQaDecisionPlanner,
)
from investory.agent_core.runtime.task_executor import TaskExecutor


NODE_CLASSIFY_REQUEST: Final[str] = "classify_request"
NODE_VALIDATE_DECISION_CONTRACT: Final[str] = "validate_decision_contract"
NODE_ASK_FOR_MISSING_INPUT: Final[str] = "ask_for_missing_input"
NODE_ANSWER_LEARNING_QUESTION: Final[str] = "answer_learning_question"
NODE_REFUSE_ADVICE_AND_REDIRECT: Final[str] = "refuse_advice_and_redirect"
NODE_BUILD_TASK_RESPONSE: Final[str] = "build_task_response"


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


class LearningQaOrchestrationFlow:
    def __init__(
        self,
        *,
        planner: LearningQaDecisionPlanner | None = None,
        router: ActionRouter | None = None,
        task_executor: TaskExecutor | None = None,
    ) -> None:
        self.planner = planner or LearningQaDecisionPlanner()
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
        try:
            final_state = self.graph.invoke(state)
            self.last_state = LearningQaFlowState.model_validate(final_state)
            if self.last_state.output is None:
                raise RuntimeError("Flow completed without output.")
            return self.last_state.output
        except Exception as exc:
            task_error = _converge_flow_error(
                exc,
                task_name=spec.name,
                request_id=request_id,
            )
            failed_result = TaskResult(
                ok=False,
                task_name=spec.name,
                error=task_error,
            )
            state.error = task_error
            state.output = failed_result
            self.last_state = state
            return failed_result

    def _build_graph(self):
        graph = StateGraph(LearningQaFlowState)
        graph.add_node(NODE_CLASSIFY_REQUEST, self._node_classify_request)
        graph.add_node(
            NODE_VALIDATE_DECISION_CONTRACT,
            self._node_validate_decision_contract,
        )
        graph.add_node(NODE_ASK_FOR_MISSING_INPUT, self._node_ask_for_missing_input)
        graph.add_node(
            NODE_ANSWER_LEARNING_QUESTION,
            self._node_answer_learning_question,
        )
        graph.add_node(
            NODE_REFUSE_ADVICE_AND_REDIRECT,
            self._node_refuse_advice_and_redirect,
        )
        graph.add_node(NODE_BUILD_TASK_RESPONSE, self._node_build_task_response)
        graph.add_edge(START, NODE_CLASSIFY_REQUEST)
        graph.add_edge(NODE_CLASSIFY_REQUEST, NODE_VALIDATE_DECISION_CONTRACT)
        graph.add_conditional_edges(
            NODE_VALIDATE_DECISION_CONTRACT,
            route_by_action_key,
            {
                ASK_MISSING_FIELDS: NODE_ASK_FOR_MISSING_INPUT,
                RUN_TASK_MODEL: NODE_ANSWER_LEARNING_QUESTION,
                REFUSE_INVESTMENT_ADVICE: NODE_REFUSE_ADVICE_AND_REDIRECT,
                NODE_BUILD_TASK_RESPONSE: NODE_BUILD_TASK_RESPONSE,
            },
        )
        graph.add_edge(NODE_ASK_FOR_MISSING_INPUT, NODE_BUILD_TASK_RESPONSE)
        graph.add_edge(NODE_ANSWER_LEARNING_QUESTION, NODE_BUILD_TASK_RESPONSE)
        graph.add_edge(NODE_REFUSE_ADVICE_AND_REDIRECT, NODE_BUILD_TASK_RESPONSE)
        graph.add_edge(NODE_BUILD_TASK_RESPONSE, END)
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
        state.action_call = validate_decision_contract(
            state.decision,
            spec,
            request_id=request_id,
        )

    def ask_for_missing_input(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
    ) -> None:
        self._execute_expected_action(state, spec, ASK_MISSING_FIELDS)

    def answer_learning_question(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
    ) -> None:
        self._execute_expected_action(state, spec, RUN_TASK_MODEL)

    def refuse_advice_and_redirect(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
    ) -> None:
        self._execute_expected_action(state, spec, REFUSE_INVESTMENT_ADVICE)

    def _execute_expected_action(
        self,
        state: LearningQaFlowState,
        spec: TaskSpec,
        expected_action: str,
    ) -> None:
        action_call = state.action_call
        if action_call is None:
            raise RuntimeError("Cannot execute action node without action_call.")
        if action_call.action != expected_action:
            raise RuntimeError(
                f"Routed to {expected_action!r} but action_call is {action_call.action!r}."
            )
        if state.decision is None:
            raise RuntimeError("Cannot execute action node without decision.")
        validate_action_params(state.decision, spec)
        executor = self.router.route(action_call)
        state.action_result = executor.execute(action_call, spec)

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

    def _node_ask_for_missing_input(
        self,
        state: LearningQaFlowState,
    ) -> dict[str, Any]:
        self.ask_for_missing_input(state, state.spec)
        return {"action_result": state.action_result}

    def _node_answer_learning_question(
        self,
        state: LearningQaFlowState,
    ) -> dict[str, Any]:
        self.answer_learning_question(state, state.spec)
        return {"action_result": state.action_result}

    def _node_refuse_advice_and_redirect(
        self,
        state: LearningQaFlowState,
    ) -> dict[str, Any]:
        self.refuse_advice_and_redirect(state, state.spec)
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


def route_by_action_key(state: LearningQaFlowState) -> str:
    if state.action_call is None:
        return NODE_BUILD_TASK_RESPONSE
    return state.action_call.action


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


def _converge_flow_error(
    exc: Exception,
    *,
    task_name: str,
    request_id: str | None,
) -> TaskError:
    if isinstance(exc, ActionValidationError):
        return TaskError(
            error_type="input_validation_failed",
            stage="input_validation",
            user_safe_message=(
                "The request could not be validated for this task. "
                "Please check the required fields and try again."
            ),
            retryable=False,
            request_id=request_id,
            debug_message=f"{task_name}: {exc}",
        )

    if isinstance(exc, ActionRoutingError):
        return TaskError(
            error_type="unknown_error",
            stage="model_call",
            user_safe_message=(
                "The request could not be routed to an execution path. "
                "Please try again later."
            ),
            retryable=False,
            request_id=request_id,
            debug_message=f"{task_name}: {exc}",
        )

    return normalize_task_error(
        exc,
        stage="model_call",
        request_id=request_id,
    )
