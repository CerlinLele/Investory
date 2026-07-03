import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewState,
)
from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    COMPLETE_ROUTE,
    CHUNK_REVIEW_SCOPE,
    FULL_DOCUMENT_REVIEW_SCOPE,
    InvestmentDocumentReviewNode,
    InvestmentDocumentReviewTodoResumeStore,
    MISSING_ROUTE,
    PENDING_APPROVAL_ROUTE,
    REFUSAL_ROUTE,
)

# Re-export route constants for graph construction
__all__ = [
    "InvestmentDocumentReviewFlow",
    "build_investment_document_review_flow",
]
from investory.agent_core.runtime.flow.investment_document_review.document_review_nodes import (
    InvestmentDocumentReviewNodeHandlers,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_router import (
    InvestmentDocumentReviewLLMRouter,
    InvestmentDocumentReviewRouter,
)
from investory.agent_core.runtime.task_executor import TaskExecutor

# Re-export constants and utilities for backward compatibility
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    ACTION_FIELD,
    AGGREGATE_ANALYZE_TASK_ID,
    APPROVAL_FIELD,
    CHUNK_COUNT_FIELD,
    CHUNK_EXTRACT_TASK_ID_PREFIX,
    CHUNK_INDEX_FIELD,
    CHUNK_REVIEW_SCOPE,
    CHUNK_REVIEW_SCOPE_FIELD,
    CLASSIFICATION_CLARIFICATION_MESSAGE,
    CRITERIA_FIELD,
    DOCUMENT_TYPE_FIELD,
    FULL_DOCUMENT_EXTRACT_TASK_ID,
    FULL_DOCUMENT_REVIEW_SCOPE,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    InvestmentDocumentReviewAction,
    MAX_ROUNDS_FIELD,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    MISSING_INPUT_MESSAGE,
    PENDING_APPROVAL_ROUTE,
    REFUSAL_MESSAGE,
    REQUIRED_ROLE_FIELD,
    REVIEW_FIELD,
    REVIEW_RESULT_FIELD,
    REVIEW_SUMMARY_FIELD,
    RISK_ASSESSMENT_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    STATUS_FIELD,
    SYNTHESIZE_REVIEW_TASK_ID,
    TODO_PLAN_FIELD,
    TODO_RESULTS_FIELD,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_todo import (
    is_chunked_document,
    should_use_chunk_review,
    should_use_code_built_plan,
)

if TYPE_CHECKING:
    from investory.agent_core.runtime.request_runner import RequestRunner


logger = logging.getLogger(__name__)


class InvestmentDocumentReviewFlow:
    """
    LangGraph-based investment document review flow.

    Responsible for constructing the state graph and orchestrating node execution.
    All node behavior is delegated to InvestmentDocumentReviewNodeHandlers.
    """

    def __init__(
        self,
        executor: TaskExecutor | None = None,
        llm_router: InvestmentDocumentReviewRouter | None = None,
        *,
        supports_realtime_data: bool = False,
        todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None = None,
    ) -> None:
        resolved_executor = executor or TaskExecutor()
        resolved_router = llm_router or InvestmentDocumentReviewLLMRouter()
        todo_runner_factory = None
        custom_todo_runner_builder = getattr(
            self,
            "_build_todo_execution_runner",
            None,
        )
        if custom_todo_runner_builder is not None:

            def todo_runner_factory(
                state: InvestmentDocumentReviewState,
                _executor: TaskExecutor,
                resume_state,
            ):
                return custom_todo_runner_builder(
                    state,
                    resume_state=resume_state,
                )

        self.nodes = InvestmentDocumentReviewNodeHandlers(
            executor=resolved_executor,
            llm_router=resolved_router,
            supports_realtime_data=supports_realtime_data,
            todo_resume_store=todo_resume_store,
            todo_runner_factory=todo_runner_factory,
        )
        self.graph = self._build_graph()

    def run(
        self,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> TaskResult:
        initial_state = InvestmentDocumentReviewState(
            session_id=session_id or str(uuid4()),
            input_payload=payload,
        )
        final_state = InvestmentDocumentReviewState.model_validate(
            self.graph.invoke(initial_state)
        )
        if final_state.output is None:
            raise RuntimeError(
                "InvestmentDocumentReviewFlow finished without TaskResult output."
            )
        return final_state.output

    def _build_graph(self):
        graph = StateGraph(InvestmentDocumentReviewState)

        graph.add_node(
            InvestmentDocumentReviewNode.EVALUATE_POLICY_GATE.value,
            self.nodes.evaluate_policy_gate,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            self.nodes.classify_document_type,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            self.nodes.build_review_framework,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.GENERATE_REVIEW_TODO_PLAN.value,
            self.nodes.generate_review_todo_plan,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.EXECUTE_REVIEW_TODO_PLAN.value,
            self.nodes.execute_review_todo_plan,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.RUN_SINGLE_PASS_REVIEW.value,
            self.nodes.run_single_pass_review,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.REFLECT_REVIEW_OUTPUT.value,
            self.nodes.reflect_review_output,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.ASSESS_REVIEW_RISK.value,
            self.nodes.assess_review_risk,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value,
            self.nodes.build_final_result,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_PENDING_APPROVAL_RESULT.value,
            self.nodes.build_pending_approval_result,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
            self.nodes.build_missing_input_result,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value,
            self.nodes.build_refusal_result,
        )

        graph.add_edge(START, InvestmentDocumentReviewNode.EVALUATE_POLICY_GATE.value)
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.EVALUATE_POLICY_GATE.value,
            self.nodes.route_after_policy_gate,
            {
                MISSING_ROUTE: InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
                REFUSAL_ROUTE: InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value,
                COMPLETE_ROUTE: InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            },
        )
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            self.nodes.route_after_classification,
            {
                MISSING_ROUTE: InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
                COMPLETE_ROUTE: InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            },
        )
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            self.nodes.route_after_review_framework,
            {
                CHUNK_REVIEW_SCOPE: InvestmentDocumentReviewNode.GENERATE_REVIEW_TODO_PLAN.value,
                FULL_DOCUMENT_REVIEW_SCOPE: InvestmentDocumentReviewNode.RUN_SINGLE_PASS_REVIEW.value,
            },
        )
        graph.add_edge(
            InvestmentDocumentReviewNode.GENERATE_REVIEW_TODO_PLAN.value,
            InvestmentDocumentReviewNode.EXECUTE_REVIEW_TODO_PLAN.value,
        )
        graph.add_edge(
            InvestmentDocumentReviewNode.EXECUTE_REVIEW_TODO_PLAN.value,
            InvestmentDocumentReviewNode.REFLECT_REVIEW_OUTPUT.value,
        )
        graph.add_edge(
            InvestmentDocumentReviewNode.RUN_SINGLE_PASS_REVIEW.value,
            InvestmentDocumentReviewNode.REFLECT_REVIEW_OUTPUT.value,
        )
        graph.add_edge(
            InvestmentDocumentReviewNode.REFLECT_REVIEW_OUTPUT.value,
            InvestmentDocumentReviewNode.ASSESS_REVIEW_RISK.value,
        )
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.ASSESS_REVIEW_RISK.value,
            self.nodes.route_after_risk_assessment,
            {
                COMPLETE_ROUTE: InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value,
                PENDING_APPROVAL_ROUTE: (
                    InvestmentDocumentReviewNode.BUILD_PENDING_APPROVAL_RESULT.value
                ),
            },
        )
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value, END)
        graph.add_edge(
            InvestmentDocumentReviewNode.BUILD_PENDING_APPROVAL_RESULT.value,
            END,
        )
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value, END)
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value, END)

        return graph.compile()


def build_investment_document_review_flow(
    executor: TaskExecutor | None = None,
    runner: "RequestRunner | None" = None,
    llm_router: InvestmentDocumentReviewRouter | None = None,
    todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None = None,
) -> InvestmentDocumentReviewFlow:
    resolved_executor = executor or TaskExecutor(runner=runner)
    resolved_router = llm_router or InvestmentDocumentReviewLLMRouter(runner=runner)
    return InvestmentDocumentReviewFlow(
        executor=resolved_executor,
        llm_router=resolved_router,
        todo_resume_store=todo_resume_store,
    )
