import asyncio
import logging
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from investory.agent_core.contracts.investment_document_review_state import (
    ANALYZE_FOCUS_FIELD,
    DOCUMENT_TEXT_FIELD,
    EXTRACT_FOCUS_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.result_types import TaskResult, normalize_task_error
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_router import (
    InvestmentDocumentReviewLLMRouter,
    InvestmentDocumentReviewRouter,
)
from investory.agent_core.runtime.flow.investment_document_review.document_chunker import (
    split_into_chunks,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    UNKNOWN_DOCUMENT_MISSING_FIELDS,
    detect_missing_fields,
    get_review_framework,
    looks_like_investment_advice,
    requires_realtime_data,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeInput,
    InvestmentDocumentReviewExtractInput,
    InvestmentDocumentReviewSynthesizeInput,
    InvestmentDocumentReviewTodoSummary,
    InvestmentDocumentReviewTodoTaskSummary,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.runtime.todo_core.plan_validator import (
    TodoPlanValidationException,
    ensure_valid_todo_plan,
)
from investory.agent_core.runtime.todo_core.runner import (
    TODO_EVENT_LAYER_STARTED,
    TODO_EVENT_TASK_FAILED,
    TODO_EVENT_TASK_RETRYING,
    TODO_EVENT_TASK_SKIPPED,
    TODO_EVENT_TASK_STARTED,
    TODO_EVENT_TASK_SUCCEEDED,
    TodoExecutionRunner,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)

if TYPE_CHECKING:
    from investory.agent_core.runtime.request_runner import RequestRunner


INVESTMENT_DOCUMENT_REVIEW_TASK_NAME = "investment_document_review"
logger = logging.getLogger(__name__)

ACTION_FIELD = "action"
MESSAGE_FIELD = "message"
DOCUMENT_TYPE_FIELD = "document_type"
REVIEW_FIELD = "review"
MISSING_FIELDS_FIELD = "missing_fields"
ROUTE_REASON_FIELD = "route_reason"
ROUTE_CONFIDENCE_FIELD = "route_confidence"

MISSING_INPUT_MESSAGE = (
    "Please provide the missing document material or a clearer document type hint "
    "so the review can continue."
)
CLASSIFICATION_CLARIFICATION_MESSAGE = (
    "Please clarify the document type or provide more review context so the "
    "document review can continue."
)
REFUSAL_MESSAGE = (
    "This flow cannot handle buy, sell, hold, timing, allocation, or real-time "
    "market requests. It can only review the provided document for facts, risks, "
    "and information gaps."
)

MISSING_ROUTE = "missing"
REFUSAL_ROUTE = "refusal"
COMPLETE_ROUTE = "complete"
CHUNK_INDEX_FIELD = "chunk_index"
CHUNK_COUNT_FIELD = "chunk_count"
CHUNK_REVIEW_SCOPE_FIELD = "review_scope"
FULL_DOCUMENT_REVIEW_SCOPE = "full_document"
CHUNK_REVIEW_SCOPE = "document_chunk"
CHUNK_EXTRACT_TASK_ID_PREFIX = "extract_chunk"
AGGREGATE_ANALYZE_TASK_ID = "analyze_aggregated_chunk_evidence"
SYNTHESIZE_REVIEW_TASK_ID = "synthesize_full_document_review"
COMPLETED_TODO_RESULT_STATUSES = {
    TodoTaskStatus.SUCCEEDED,
    TodoTaskStatus.FAILED,
    TodoTaskStatus.SKIPPED,
}


class InvestmentDocumentReviewAction(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    COMPLETE = "complete"


class InvestmentDocumentReviewNode(str, Enum):
    EVALUATE_POLICY_GATE = "evaluate_policy_gate"
    CLASSIFY_DOCUMENT_TYPE = "classify_document_type"
    BUILD_REVIEW_FRAMEWORK = "build_review_framework"
    GENERATE_REVIEW_TODO_PLAN = "generate_review_todo_plan"
    EXECUTE_REVIEW_TODO_PLAN = "execute_review_todo_plan"
    RUN_SINGLE_PASS_REVIEW = "run_single_pass_review"
    BUILD_FINAL_RESULT = "build_final_result"
    BUILD_MISSING_INPUT_RESULT = "build_missing_input_result"
    BUILD_REFUSAL_RESULT = "build_refusal_result"


class InvestmentDocumentReviewTodoResumeStore(Protocol):
    def load_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
    ) -> TodoExecutionResumeState | None: ...

    def save_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
        results: list[TodoTaskResult],
        previous_resume_state: TodoExecutionResumeState | None,
    ) -> None: ...


def _build_completed_todo_results(
    todo_plan: TodoExecutionPlan,
    results_by_id: dict[str, TodoTaskResult],
) -> list[TodoTaskResult]:
    completed_results_by_id = {
        result.id: result
        for result in results_by_id.values()
        if result.status in COMPLETED_TODO_RESULT_STATUSES
    }
    planned_task_ids = [task.id for task in todo_plan.tasks]
    ordered_results = [
        completed_results_by_id[task_id]
        for task_id in planned_task_ids
        if task_id in completed_results_by_id
    ]
    ordered_results.extend(
        result
        for task_id, result in completed_results_by_id.items()
        if task_id not in planned_task_ids
    )
    return ordered_results


def _find_succeeded_todo_result(
    todo_results: list[TodoTaskResult],
    task_id: str,
) -> TodoTaskResult | None:
    for result in todo_results:
        if result.id == task_id and result.status == TodoTaskStatus.SUCCEEDED:
            return result
    return None


def _build_review_todo_summary(
    *,
    todo_plan: TodoExecutionPlan,
    completed_results: list[TodoTaskResult],
) -> InvestmentDocumentReviewTodoSummary:
    tasks_by_id = {task.id: task for task in todo_plan.tasks}
    succeeded_task_ids: list[str] = []
    failed_task_ids: list[str] = []
    skipped_task_ids: list[str] = []
    extracted_facts: list[str] = []
    risk_findings: list[str] = []
    information_gaps: list[str] = []
    boundary_notes: list[str] = []
    task_summaries: list[InvestmentDocumentReviewTodoTaskSummary] = []

    for result in completed_results:
        task = tasks_by_id.get(result.id)
        if result.status == TodoTaskStatus.SUCCEEDED:
            succeeded_task_ids.append(result.id)
            result_payload = result.result or {}
            extracted_facts.extend(_string_list_from_result(result_payload, "extracted_facts"))
            risk_findings.extend(_string_list_from_result(result_payload, "risk_findings"))
            information_gaps.extend(
                _string_list_from_result(result_payload, "information_gaps")
            )
            boundary_notes.extend(_string_list_from_result(result_payload, "boundary_notes"))
            summary = _string_from_result(result_payload, "summary")
        elif result.status == TodoTaskStatus.FAILED:
            failed_task_ids.append(result.id)
            summary = _todo_result_error_message(result)
            information_gaps.append(
                _todo_incomplete_review_note(
                    result=result,
                    task_title=task.title if task is not None else None,
                )
            )
        else:
            skipped_task_ids.append(result.id)
            summary = _todo_result_error_message(result)
            boundary_notes.append(
                _todo_incomplete_review_note(
                    result=result,
                    task_title=task.title if task is not None else None,
                )
            )

        task_summaries.append(
            InvestmentDocumentReviewTodoTaskSummary(
                task_id=result.id,
                task_title=task.title if task is not None else None,
                task_kind=task.kind if task is not None else None,
                status=result.status,
                summary=summary,
            )
        )

    return InvestmentDocumentReviewTodoSummary(
        plan_summary=todo_plan.summary,
        planned_task_count=len(todo_plan.tasks),
        completed_task_count=len(completed_results),
        succeeded_task_ids=succeeded_task_ids,
        failed_task_ids=failed_task_ids,
        skipped_task_ids=skipped_task_ids,
        extracted_facts=extracted_facts,
        risk_findings=risk_findings,
        information_gaps=information_gaps,
        boundary_notes=boundary_notes,
        task_summaries=task_summaries,
    )


def _log_review_todo_plan_generated(
    *,
    session_id: str | None,
    todo_plan: TodoExecutionPlan,
    document_type: InvestmentDocumentType | None,
    chunk_count: int,
) -> None:
    logger.info(
        "investment_document_review.todo_plan.generated session_id=%s document_type=%s "
        "chunk_count=%s task_count=%s failure_policy=%s summary=%s",
        session_id,
        document_type.value if document_type is not None else None,
        chunk_count,
        len(todo_plan.tasks),
        todo_plan.failure_policy.value,
        todo_plan.summary,
    )
    for task in todo_plan.tasks:
        logger.debug(
            "investment_document_review.todo_plan.task session_id=%s task_id=%s "
            "task_kind=%s title=%s depends_on=%s completion_criteria_count=%s",
            session_id,
            task.id,
            task.kind.value,
            task.title,
            ",".join(task.depends_on) if task.depends_on else "",
            len(task.completion_criteria),
        )


def _guess_review_plan_chunk_count(state: InvestmentDocumentReviewState) -> int:
    return len(state.document_chunks or [])


def _build_review_todo_runner_event_handler(
    *,
    session_id: str | None,
) -> Callable[[str, dict[str, Any]], None]:
    def handle_event(event_name: str, payload: dict[str, Any]) -> None:
        if event_name == TODO_EVENT_LAYER_STARTED:
            logger.debug(
                "investment_document_review.todo_layer.started session_id=%s layer_index=%s task_ids=%s",
                session_id,
                payload.get("layer_index"),
                ",".join(payload.get("task_ids", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_STARTED:
            logger.info(
                "investment_document_review.todo_task.started session_id=%s task_id=%s task_kind=%s depends_on=%s attempt=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                ",".join(payload.get("depends_on", [])),
                payload.get("attempt"),
            )
            return

        if event_name == TODO_EVENT_TASK_RETRYING:
            logger.info(
                "investment_document_review.todo_task.retrying session_id=%s task_id=%s task_kind=%s attempt=%s next_attempt=%s max_attempts=%s error_type=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("attempt"),
                payload.get("next_attempt"),
                payload.get("max_attempts"),
                payload.get("error_type"),
            )
            return

        if event_name == TODO_EVENT_TASK_SUCCEEDED:
            logger.info(
                "investment_document_review.todo_task.succeeded session_id=%s task_id=%s task_kind=%s duration_ms=%s result_keys=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                ",".join(payload.get("result_keys", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_FAILED:
            logger.warning(
                "investment_document_review.todo_task.failed session_id=%s task_id=%s task_kind=%s duration_ms=%s error_type=%s stage=%s result_keys=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                payload.get("error_type"),
                payload.get("stage"),
                ",".join(payload.get("result_keys", [])),
            )
            return

        if event_name == TODO_EVENT_TASK_SKIPPED:
            reason = _todo_task_skip_reason(payload.get("error_type"))
            logger.info(
                "investment_document_review.todo_task.skipped session_id=%s task_id=%s task_kind=%s duration_ms=%s reason=%s stage=%s failed_dependency_task_id=%s",
                session_id,
                payload.get("task_id"),
                payload.get("task_kind"),
                payload.get("duration_ms"),
                reason,
                payload.get("stage"),
                payload.get("failed_dependency_task_id"),
            )

    return handle_event


def _todo_task_skip_reason(error_type: Any) -> str | None:
    if not isinstance(error_type, str):
        return None
    return error_type


def _string_list_from_result(result_payload: dict[str, Any], key: str) -> list[str]:
    value = result_payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_from_result(result_payload: dict[str, Any], key: str) -> str | None:
    value = result_payload.get(key)
    if isinstance(value, str):
        return value
    return None


def _todo_result_error_message(result: TodoTaskResult) -> str | None:
    if result.error is None:
        return None
    message = result.error.get("message")
    if isinstance(message, str):
        return message
    return None


def _todo_incomplete_review_note(
    *,
    result: TodoTaskResult,
    task_title: str | None,
) -> str:
    task_label = task_title or result.id
    reason = _todo_result_error_message(result)
    if reason:
        return f"{task_label} ({result.id}) did not complete: {reason}"
    return f"{task_label} ({result.id}) did not complete with status {result.status.value}."


class InvestmentDocumentReviewFlow:
    def __init__(
        self,
        executor: TaskExecutor | None = None,
        llm_router: InvestmentDocumentReviewRouter | None = None,
        *,
        supports_realtime_data: bool = False,
        todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None = None,
    ) -> None:
        self.executor = executor or TaskExecutor()
        self.llm_router = llm_router or InvestmentDocumentReviewLLMRouter()
        self.supports_realtime_data = supports_realtime_data
        self.todo_resume_store = todo_resume_store
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
            self.evaluate_policy_gate,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            self.classify_document_type,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            self.build_review_framework,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.GENERATE_REVIEW_TODO_PLAN.value,
            self.generate_review_todo_plan,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.EXECUTE_REVIEW_TODO_PLAN.value,
            self.execute_review_todo_plan,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.RUN_SINGLE_PASS_REVIEW.value,
            self.run_single_pass_review,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value,
            self.build_final_result,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
            self.build_missing_input_result,
        )
        graph.add_node(
            InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value,
            self.build_refusal_result,
        )

        graph.add_edge(START, InvestmentDocumentReviewNode.EVALUATE_POLICY_GATE.value)
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.EVALUATE_POLICY_GATE.value,
            self.route_after_policy_gate,
            {
                MISSING_ROUTE: InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
                REFUSAL_ROUTE: InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value,
                COMPLETE_ROUTE: InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            },
        )
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.CLASSIFY_DOCUMENT_TYPE.value,
            self.route_after_classification,
            {
                MISSING_ROUTE: InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value,
                COMPLETE_ROUTE: InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            },
        )
        graph.add_conditional_edges(
            InvestmentDocumentReviewNode.BUILD_REVIEW_FRAMEWORK.value,
            self.route_after_review_framework,
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
            InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value,
        )
        graph.add_edge(
            InvestmentDocumentReviewNode.RUN_SINGLE_PASS_REVIEW.value,
            InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value,
        )
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_FINAL_RESULT.value, END)
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_MISSING_INPUT_RESULT.value, END)
        graph.add_edge(InvestmentDocumentReviewNode.BUILD_REFUSAL_RESULT.value, END)

        return graph.compile()

    def evaluate_policy_gate(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        return {"missing_fields": detect_missing_fields(state.input_payload)}

    def route_after_policy_gate(self, state: InvestmentDocumentReviewState) -> str:
        if state.missing_fields:
            return MISSING_ROUTE

        if looks_like_investment_advice(state.input_payload):
            return REFUSAL_ROUTE

        if (
            requires_realtime_data(state.input_payload)
            and not self.supports_realtime_data
        ):
            return REFUSAL_ROUTE

        return COMPLETE_ROUTE

    def classify_document_type(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        decision = self.llm_router.route(state.input_payload)
        missing_fields = decision.missing_fields
        if decision.document_type == InvestmentDocumentType.UNKNOWN and not missing_fields:
            missing_fields = UNKNOWN_DOCUMENT_MISSING_FIELDS
        return {
            "document_type": decision.document_type,
            "route_reason": decision.reason,
            "route_confidence": decision.confidence,
            "missing_fields": missing_fields,
        }

    def route_after_classification(
        self,
        state: InvestmentDocumentReviewState,
    ) -> str:
        if state.document_type == InvestmentDocumentType.UNKNOWN:
            return MISSING_ROUTE

        if state.missing_fields:
            return MISSING_ROUTE

        return COMPLETE_ROUTE

    def build_review_framework(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.document_type is None:
            raise RuntimeError("Document review flow has no classified document type.")

        review_framework = get_review_framework(state.document_type)
        if review_framework is None:
            raise RuntimeError(
                f"Document review flow has no framework for {state.document_type.value}."
            )

        review_payload = {
            DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
            DOCUMENT_TYPE_FIELD: state.document_type,
            EXTRACT_FOCUS_FIELD: review_framework.extract_focus,
            ANALYZE_FOCUS_FIELD: review_framework.analyze_focus,
            REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
        }

        document_text = state.input_payload.get(DOCUMENT_TEXT_FIELD) or ""
        document_chunks = split_into_chunks(document_text) if document_text else []

        return {
            "review_framework": review_framework,
            "review_payload": review_payload,
            "document_chunks": document_chunks,
        }

    def route_after_review_framework(self, state: InvestmentDocumentReviewState) -> str:
        if state.document_chunks:
            return CHUNK_REVIEW_SCOPE
        return FULL_DOCUMENT_REVIEW_SCOPE

    def run_single_pass_review(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        result = self.executor.run(
            INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
            state.review_payload or state.input_payload,
        )
        return {"output": result}

    def generate_review_todo_plan(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.document_chunks:
            todo_plan = self._build_chunk_review_todo_plan(state)
            _log_review_todo_plan_generated(
                session_id=state.session_id,
                todo_plan=todo_plan,
                document_type=state.document_type,
                chunk_count=_guess_review_plan_chunk_count(state),
            )
            return {"todo_plan": todo_plan}

        plan_payload = self.build_review_todo_plan_payload(state)
        result = self.executor.run(
            INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
            plan_payload,
        )
        if not result.ok:
            return {"output": result}

        try:
            todo_plan = TodoExecutionPlan.model_validate(result.result)
            ensure_valid_todo_plan(todo_plan)
        except (ValidationError, TodoPlanValidationException) as exc:
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                    error=normalize_task_error(exc, stage="output_validation"),
                )
            }

        _log_review_todo_plan_generated(
            session_id=state.session_id,
            todo_plan=todo_plan,
            document_type=state.document_type,
            chunk_count=_guess_review_plan_chunk_count(state),
        )
        return {"todo_plan": todo_plan}

    def _build_chunk_review_todo_plan(
        self,
        state: InvestmentDocumentReviewState,
    ) -> TodoExecutionPlan:
        if state.review_payload is None:
            raise RuntimeError("Document review flow has no review payload for chunk review.")

        chunk_count = len(state.document_chunks)
        extract_task_ids = [
            f"{CHUNK_EXTRACT_TASK_ID_PREFIX}_{idx + 1:04d}"
            for idx in range(chunk_count)
        ]
        extract_focus = state.review_payload.get(EXTRACT_FOCUS_FIELD) or []
        analyze_focus = state.review_payload.get(ANALYZE_FOCUS_FIELD) or []
        tasks = [
            {
                "id": task_id,
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                "title": f"Extract evidence from document chunk {idx + 1} of {chunk_count}",
                "description": (
                    "Extract lightweight, document-grounded evidence from this chunk: "
                    "key facts, fees, risks, constraints, disclosures, gaps, unusual "
                    "statements, and source citations."
                ),
                "payload": {
                    DOCUMENT_TEXT_FIELD: chunk,
                    EXTRACT_FOCUS_FIELD: extract_focus,
                    CHUNK_INDEX_FIELD: idx,
                    CHUNK_COUNT_FIELD: chunk_count,
                    CHUNK_REVIEW_SCOPE_FIELD: CHUNK_REVIEW_SCOPE,
                },
                "depends_on": [],
                "completion_criteria": [
                    "Output contains only facts and evidence visible in this chunk.",
                    "Important missing or weak evidence is recorded as information gaps.",
                    "Source citations identify the supporting chunk text or section.",
                ],
            }
            for idx, (task_id, chunk) in enumerate(
                zip(extract_task_ids, state.document_chunks, strict=True)
            )
        ]
        tasks.extend(
            [
                {
                    "id": AGGREGATE_ANALYZE_TASK_ID,
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze aggregated chunk evidence",
                    "description": (
                        "Merge evidence extracted from every document chunk and analyze "
                        "risks, disclosure quality, inconsistencies, constraints, and gaps."
                    ),
                    "payload": {ANALYZE_FOCUS_FIELD: analyze_focus},
                    "depends_on": extract_task_ids,
                    "completion_criteria": [
                        "Findings are based only on successful chunk extraction results.",
                        "Cross-chunk conflicts, limitations, and disclosure gaps are identified.",
                    ],
                },
                {
                    "id": SYNTHESIZE_REVIEW_TASK_ID,
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                    "title": "Synthesize full-document review",
                    "description": (
                        "Produce the final investment document review from the aggregated "
                        "chunk evidence and analysis results."
                    ),
                    "payload": {},
                    "depends_on": [AGGREGATE_ANALYZE_TASK_ID],
                    "completion_criteria": [
                        "Final review covers extracted evidence from all document chunks.",
                        "Facts, risks, gaps, boundary notes, and summary are supported by task results.",
                    ],
                },
            ]
        )
        return TodoExecutionPlan.model_validate(
            {
                "tasks": tasks,
                "summary": (
                    "Extract lightweight evidence from every document chunk, aggregate the "
                    "evidence by review theme, then synthesize the full document review."
                ),
            }
        )

    def execute_review_todo_plan(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.todo_plan is None:
            raise RuntimeError("Document review flow has no To-Do plan to execute.")

        resume_state = self._load_todo_resume_state(state)
        runner = self._build_todo_execution_runner(
            state,
            resume_state=resume_state,
        )
        todo_results = asyncio.run(
            runner.run(state.todo_plan, resume_state=resume_state)
        )
        self._save_todo_resume_state(
            state=state,
            todo_results=todo_results,
            previous_resume_state=resume_state,
        )
        update: dict[str, Any] = {"todo_results": todo_results}
        synthesize_result = _find_succeeded_todo_result(
            todo_results,
            SYNTHESIZE_REVIEW_TASK_ID,
        )
        if synthesize_result is not None:
            update["output"] = TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                result=synthesize_result.result,
            )
        elif state.document_chunks:
            update["output"] = TaskResult(
                ok=False,
                task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                error=normalize_task_error(
                    RuntimeError("Chunk-based document review did not produce synthesis."),
                    stage="output_validation",
                ),
            )
        return update

    def _load_todo_resume_state(
        self,
        state: InvestmentDocumentReviewState,
    ) -> TodoExecutionResumeState | None:
        if self.todo_resume_store is None:
            return None

        if state.session_id is None:
            return None

        if state.todo_plan is None:
            raise RuntimeError("Document review flow has no To-Do plan to resume.")

        return self.todo_resume_store.load_resume_state(
            session_id=state.session_id,
            plan=state.todo_plan,
        )

    def _save_todo_resume_state(
        self,
        *,
        state: InvestmentDocumentReviewState,
        todo_results: list[TodoTaskResult],
        previous_resume_state: TodoExecutionResumeState | None,
    ) -> None:
        if self.todo_resume_store is None:
            return

        if state.session_id is None:
            return

        if state.todo_plan is None:
            raise RuntimeError("Document review flow has no To-Do plan to persist.")

        self.todo_resume_store.save_resume_state(
            session_id=state.session_id,
            plan=state.todo_plan,
            results=todo_results,
            previous_resume_state=previous_resume_state,
        )

    def _build_todo_execution_runner(
        self,
        state: InvestmentDocumentReviewState,
        *,
        resume_state: TodoExecutionResumeState | None = None,
    ) -> TodoExecutionRunner:
        executed_results_by_id = {result.id: result for result in state.todo_results}
        if resume_state is not None:
            executed_results_by_id.update(resume_state.results_by_id)

        async def execute(task) -> TodoTaskResult:
            result = await self._execute_review_todo_task(
                state=state,
                task=task,
                executed_results_by_id=executed_results_by_id,
            )
            executed_results_by_id[result.id] = result
            return result

        return TodoExecutionRunner(
            execute,
            event_handler=_build_review_todo_runner_event_handler(
                session_id=state.session_id,
            ),
        )

    async def _execute_review_todo_task(
        self,
        *,
        state,
        task,
        executed_results_by_id: dict[str, TodoTaskResult],
    ) -> TodoTaskResult:
        try:
            spec, payload = self._build_review_todo_task_execution(
                state=state,
                task=task,
                executed_results_by_id=executed_results_by_id,
            )
        except RuntimeError as exc:
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.FAILED,
                error={
                    "error_type": "todo_task_payload_not_supported",
                    "message": str(exc),
                    "details": {"task_kind": task.kind.value},
                },
            )

        result = self.executor.run(spec, payload)
        if result.ok:
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.SUCCEEDED,
                result=result.result,
            )

        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "todo_task_execution_failed",
                "message": (
                    result.error.user_safe_message
                    if result.error is not None
                    else "The To-Do task failed to run."
                ),
                "details": {
                    "task_name": spec.name,
                    "task_kind": task.kind.value,
                    "stage": result.error.stage if result.error is not None else None,
                    "debug_message": (
                        result.error.debug_message if result.error is not None else None
                    ),
                },
            },
        )

    def _build_review_todo_task_execution(
        self,
        *,
        state: InvestmentDocumentReviewState,
        task,
        executed_results_by_id: dict[str, TodoTaskResult],
    ) -> tuple[Any, dict[str, Any]]:
        if state.document_type is None:
            raise RuntimeError("Document review flow has no classified document type.")

        if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT:
            return (
                INVESTMENT_DOCUMENT_EXTRACT_TASK,
                self._build_review_todo_extract_payload(state=state, task=task),
            )

        if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE:
            return (
                INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
                self._build_review_todo_synthesize_payload(
                    state=state,
                    executed_results_by_id=executed_results_by_id,
                ),
            )

        if task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE:
            return (
                INVESTMENT_DOCUMENT_ANALYZE_TASK,
                self._build_review_todo_analyze_payload(
                    state=state,
                    task=task,
                    dependency_results=self._build_review_todo_dependency_results(
                        task=task,
                        executed_results_by_id=executed_results_by_id,
                    ),
                ),
            )

        raise RuntimeError(f"Unsupported investment document To-Do task kind: {task.kind.value}")

    def _build_review_todo_common_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
        task,
    ) -> dict[str, Any]:
        return {
            "task_id": task.id,
            "task_title": task.title,
            "task_description": task.description,
            "completion_criteria": task.completion_criteria,
            DOCUMENT_TYPE_FIELD: state.document_type,
            REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
        }

    def _build_review_todo_extract_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
        task,
    ) -> dict[str, Any]:
        return InvestmentDocumentReviewExtractInput.model_validate(
            {
                **self._build_review_todo_common_payload(state=state, task=task),
                DOCUMENT_TEXT_FIELD: task.payload.get(
                    DOCUMENT_TEXT_FIELD,
                    state.input_payload.get(DOCUMENT_TEXT_FIELD),
                ),
                EXTRACT_FOCUS_FIELD: task.payload.get(EXTRACT_FOCUS_FIELD, []),
                CHUNK_INDEX_FIELD: task.payload.get(CHUNK_INDEX_FIELD),
                CHUNK_COUNT_FIELD: task.payload.get(CHUNK_COUNT_FIELD),
                CHUNK_REVIEW_SCOPE_FIELD: task.payload.get(
                    CHUNK_REVIEW_SCOPE_FIELD,
                    FULL_DOCUMENT_REVIEW_SCOPE,
                ),
            }
        ).model_dump(exclude_none=True, exclude_defaults=True)

    def _build_review_todo_analyze_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
        task,
        dependency_results: list[TodoTaskResult],
    ) -> dict[str, Any]:
        return InvestmentDocumentReviewAnalyzeInput.model_validate(
            {
                **self._build_review_todo_common_payload(state=state, task=task),
                DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
                ANALYZE_FOCUS_FIELD: task.payload.get(ANALYZE_FOCUS_FIELD, []),
                "dependency_results": [result.model_dump() for result in dependency_results],
            }
        ).model_dump()

    def _build_review_todo_dependency_results(
        self,
        *,
        task,
        executed_results_by_id: dict[str, TodoTaskResult],
    ) -> list[TodoTaskResult]:
        if not task.depends_on:
            raise RuntimeError(
                "Analyze To-Do tasks must depend on at least one upstream task result."
            )

        dependency_results: list[TodoTaskResult] = []
        missing_dependency_ids: list[str] = []
        failed_dependency_ids: list[str] = []

        for dependency_task_id in task.depends_on:
            dependency_result = executed_results_by_id.get(dependency_task_id)
            if dependency_result is None:
                missing_dependency_ids.append(dependency_task_id)
                continue
            if dependency_result.status != TodoTaskStatus.SUCCEEDED:
                failed_dependency_ids.append(dependency_task_id)
                continue
            dependency_results.append(dependency_result)

        if missing_dependency_ids:
            raise RuntimeError(
                "Analyze To-Do task is missing required dependency results: "
                + ", ".join(missing_dependency_ids)
            )

        if failed_dependency_ids:
            raise RuntimeError(
                "Analyze To-Do task has non-succeeded dependency results: "
                + ", ".join(failed_dependency_ids)
            )

        return dependency_results

    def _build_review_todo_synthesize_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
        executed_results_by_id: dict[str, TodoTaskResult],
    ) -> dict[str, Any]:
        if state.todo_plan is None:
            raise RuntimeError("Document review flow has no To-Do plan to synthesize.")

        completed_results = _build_completed_todo_results(
            state.todo_plan,
            executed_results_by_id,
        )
        return InvestmentDocumentReviewSynthesizeInput.model_validate(
            {
                DOCUMENT_TYPE_FIELD: state.document_type,
                ROUTE_REASON_FIELD: state.route_reason or "",
                ROUTE_CONFIDENCE_FIELD: state.route_confidence or 0.0,
                REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
                "todo_plan": state.todo_plan.model_dump(),
                "todo_results": [result.model_dump() for result in completed_results],
                "review_summary": _build_review_todo_summary(
                    todo_plan=state.todo_plan,
                    completed_results=completed_results,
                ).model_dump(),
            }
        ).model_dump()

    def build_review_todo_plan_payload(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.review_payload is None:
            raise RuntimeError("Document review flow has no review payload to plan.")

        return {
            DOCUMENT_TEXT_FIELD: state.review_payload.get(DOCUMENT_TEXT_FIELD),
            DOCUMENT_TYPE_FIELD: state.review_payload.get(DOCUMENT_TYPE_FIELD),
            EXTRACT_FOCUS_FIELD: state.review_payload.get(EXTRACT_FOCUS_FIELD),
            ANALYZE_FOCUS_FIELD: state.review_payload.get(ANALYZE_FOCUS_FIELD),
            REVIEW_GOAL_FIELD: state.review_payload.get(REVIEW_GOAL_FIELD),
        }

    def build_final_result(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.output is None:
            raise RuntimeError("Document review flow has no review result to finalize.")

        if not state.output.ok:
            return {"output": state.output}

        document_type = state.document_type
        if document_type is None:
            raise RuntimeError(
                "Document review flow finished without a classified document type."
            )

        result = TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={
                ACTION_FIELD: InvestmentDocumentReviewAction.COMPLETE.value,
                DOCUMENT_TYPE_FIELD: document_type.value,
                ROUTE_REASON_FIELD: state.route_reason,
                ROUTE_CONFIDENCE_FIELD: state.route_confidence,
                REVIEW_FIELD: state.output.result,
            },
        )
        return {"output": result}

    def build_missing_input_result(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        message = (
            MISSING_INPUT_MESSAGE
            if state.missing_fields
            else CLASSIFICATION_CLARIFICATION_MESSAGE
        )
        result = TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={
                ACTION_FIELD: InvestmentDocumentReviewAction.ASK_FOR_MISSING_INPUT.value,
                MISSING_FIELDS_FIELD: state.missing_fields,
                MESSAGE_FIELD: message,
            },
        )
        return {"output": result}

    def build_refusal_result(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        result = TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={
                ACTION_FIELD: InvestmentDocumentReviewAction.REFUSE_AND_REDIRECT.value,
                MESSAGE_FIELD: REFUSAL_MESSAGE,
            },
        )
        return {"output": result}


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
