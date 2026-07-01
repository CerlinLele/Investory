"""
Investment Document Review Flow Node Handlers.

This module contains the execution logic for all LangGraph nodes in the
investment document review flow. It separates node behavior from graph structure.
"""

import logging
from typing import Any
from uuid import uuid4

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
from investory.agent_core.runtime.flow.investment_document_review.document_review_constants import (
    ACTION_FIELD,
    CLASSIFICATION_CLARIFICATION_MESSAGE,
    COMPLETE_ROUTE,
    CHUNK_REVIEW_SCOPE,
    CRITERIA_FIELD,
    DEFAULT_REFLECTION_MAX_ROUNDS,
    DOCUMENT_TYPE_FIELD,
    FULL_DOCUMENT_REVIEW_SCOPE,
    INVESTMENT_DOCUMENT_REVIEW_REFLECTION_CRITERIA,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    InvestmentDocumentReviewAction,
    InvestmentDocumentReviewTodoResumeStore,
    MAX_ROUNDS_FIELD,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    MISSING_INPUT_MESSAGE,
    MISSING_ROUTE,
    PENDING_APPROVAL_ROUTE,
    REFUSAL_MESSAGE,
    REFUSAL_ROUTE,
    REQUIRED_ROLE_FIELD,
    REVIEW_FIELD,
    REVIEW_RESULT_FIELD,
    REVIEW_SUMMARY_FIELD,
    RISK_ASSESSMENT_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    STATUS_FIELD,
    TODO_PLAN_FIELD,
    TODO_RESULTS_FIELD,
    APPROVAL_FIELD,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_router import (
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
from investory.agent_core.runtime.flow.investment_document_review.document_review_todo import (
    execute_review_todo_plan,
    generate_review_todo_plan,
    should_use_chunk_review,
)
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewApprovalStatus,
    InvestmentDocumentReviewRiskAssessmentInput,
    InvestmentDocumentReviewRiskAssessmentResult,
    InvestmentDocumentReviewResult,
)
from investory.agent_core.task_models.investment_document_review_reflection import (
    InvestmentDocumentReviewReflectionInput,
    InvestmentDocumentReviewReflectionResult,
)
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
)


logger = logging.getLogger(__name__)


def _log_review_reflection_started(
    *,
    session_id: str | None,
) -> None:
    logger.info(
        "investment_document_review.reflection.started session_id=%s",
        session_id,
    )


def _log_review_reflection_completed(
    *,
    session_id: str | None,
    reflection: InvestmentDocumentReviewReflectionResult,
) -> None:
    logger.info(
        "investment_document_review.reflection.completed session_id=%s "
        "passed=%s score=%s rounds=%s issue_count=%s safety_flag_count=%s",
        session_id,
        str(reflection.passed).lower(),
        reflection.score,
        reflection.rounds,
        len(reflection.issues),
        len(reflection.safety_flags),
    )


def _log_review_reflection_failed(
    *,
    session_id: str | None,
    stage: str,
    error_type: str | None,
) -> None:
    logger.warning(
        "investment_document_review.reflection.failed session_id=%s stage=%s "
        "error_type=%s",
        session_id,
        stage,
        error_type,
    )


def _build_review_task_status_summary(
    *,
    review_result: InvestmentDocumentReviewResult,
) -> list[str]:
    """Build task status summary for single-pass review"""
    task_status_summary = ["single_pass_review | succeeded"]
    if review_result.summary:
        task_status_summary[0] = (
            f"single_pass_review | succeeded | {review_result.summary}"
        )
    return task_status_summary


class InvestmentDocumentReviewNodeHandlers:
    """
    Node execution handlers for investment document review flow.
    
    This class encapsulates all node behavior logic, keeping the flow builder
    focused solely on graph structure and routing.
    """

    def __init__(
        self,
        *,
        executor: TaskExecutor,
        llm_router: InvestmentDocumentReviewRouter,
        supports_realtime_data: bool,
        todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None,
    ) -> None:
        self.executor = executor
        self.llm_router = llm_router
        self.supports_realtime_data = supports_realtime_data
        self.todo_resume_store = todo_resume_store

    # =========================================================================
    # Policy Gate / Classification / Framework
    # =========================================================================

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
        if should_use_chunk_review(state):
            return CHUNK_REVIEW_SCOPE
        return FULL_DOCUMENT_REVIEW_SCOPE

    # =========================================================================
    # Review / Todo / Reflection / Risk
    # =========================================================================

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
        """Delegate to todo module's plan generation logic"""
        return generate_review_todo_plan(
            state=state,
            executor=self.executor,
        )

    def execute_review_todo_plan(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        """Delegate to todo module's plan execution logic"""
        return execute_review_todo_plan(
            state=state,
            executor=self.executor,
            todo_resume_store=self.todo_resume_store,
        )

    def reflect_review_output(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.output is None or not state.output.ok:
            return {}

        try:
            payload = self._build_review_reflection_payload(state=state)
        except (RuntimeError, ValidationError) as exc:
            task_error = normalize_task_error(exc, stage="output_validation")
            _log_review_reflection_failed(
                session_id=state.session_id,
                stage=task_error.stage,
                error_type=task_error.error_type,
            )
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
                    error=task_error,
                )
            }

        _log_review_reflection_started(session_id=state.session_id)
        result = self.executor.run(INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK, payload)
        if not result.ok:
            _log_review_reflection_failed(
                session_id=state.session_id,
                stage=result.error.stage if result.error is not None else "unknown",
                error_type=(
                    result.error.error_type if result.error is not None else None
                ),
            )
            return {"output": result}

        try:
            reflection = InvestmentDocumentReviewReflectionResult.model_validate(
                result.result
            )
        except ValidationError as exc:
            task_error = normalize_task_error(exc, stage="output_validation")
            _log_review_reflection_failed(
                session_id=state.session_id,
                stage=task_error.stage,
                error_type=task_error.error_type,
            )
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
                    error=task_error,
                )
            }

        _log_review_reflection_completed(
            session_id=state.session_id,
            reflection=reflection,
        )
        return {
            "output": TaskResult(
                ok=True,
                task_name=state.output.task_name,
                result=reflection.review_result.model_dump(mode="json"),
            ),
            "reflection_result": reflection.model_dump(mode="json"),
            "reflection_passed": reflection.passed,
            "reflection_rounds": reflection.rounds,
        }

    def assess_review_risk(
        self,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.output is None:
            raise RuntimeError("Document review flow has no review result to assess.")

        if not state.output.ok:
            return {}

        try:
            payload = self._build_review_risk_assessment_payload(state=state)
        except RuntimeError as exc:
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
                    error=normalize_task_error(exc, stage="output_validation"),
                )
            }

        result = self.executor.run(INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK, payload)
        if not result.ok:
            return {"output": result}

        try:
            risk_assessment = InvestmentDocumentReviewRiskAssessmentResult.model_validate(
                result.result
            )
        except ValidationError as exc:
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
                    error=normalize_task_error(exc, stage="output_validation"),
                )
            }

        return {
            "risk_assessment": risk_assessment.model_dump(mode="json"),
            "approval_status": risk_assessment.approval_status.value,
            "approval_required_role": risk_assessment.required_role,
        }

    def route_after_risk_assessment(
        self,
        state: InvestmentDocumentReviewState,
    ) -> str:
        if state.output is None or not state.output.ok:
            return COMPLETE_ROUTE
        if (
            state.approval_status
            == InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
        ):
            return PENDING_APPROVAL_ROUTE
        return COMPLETE_ROUTE

    # =========================================================================
    # Final Result Builders
    # =========================================================================

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

        if state.risk_assessment is None:
            raise RuntimeError(
                "Document review flow finished without a risk assessment result."
            )
        if state.approval_status is None:
            raise RuntimeError(
                "Document review flow finished without an approval status."
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
                RISK_ASSESSMENT_FIELD: state.risk_assessment,
                APPROVAL_FIELD: {
                    STATUS_FIELD: state.approval_status,
                    REQUIRED_ROLE_FIELD: state.approval_required_role,
                },
            },
        )
        return {"output": result}

    def build_pending_approval_result(
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

        if state.risk_assessment is None:
            raise RuntimeError(
                "Document review flow finished without a risk assessment result."
            )
        if state.approval_status is None:
            raise RuntimeError(
                "Document review flow finished without an approval status."
            )

        result = TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={
                ACTION_FIELD: (
                    InvestmentDocumentReviewAction.PENDING_HUMAN_APPROVAL.value
                ),
                DOCUMENT_TYPE_FIELD: document_type.value,
                ROUTE_REASON_FIELD: state.route_reason,
                ROUTE_CONFIDENCE_FIELD: state.route_confidence,
                REVIEW_FIELD: state.output.result,
                RISK_ASSESSMENT_FIELD: state.risk_assessment,
                APPROVAL_FIELD: {
                    STATUS_FIELD: state.approval_status,
                    REQUIRED_ROLE_FIELD: state.approval_required_role,
                },
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

    # =========================================================================
    # Private Payload Builders
    # =========================================================================

    def _build_review_reflection_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.document_type is None:
            raise RuntimeError("Document review flow has no classified document type.")

        if state.output is None or not state.output.ok:
            raise RuntimeError("Document review flow has no successful review result.")

        review_result = InvestmentDocumentReviewResult.model_validate(
            state.output.result
        )

        payload: dict[str, Any] = {
            DOCUMENT_TYPE_FIELD: state.document_type,
            ROUTE_CONFIDENCE_FIELD: state.route_confidence or 0.0,
            REVIEW_GOAL_FIELD: state.input_payload.get(REVIEW_GOAL_FIELD),
            REVIEW_RESULT_FIELD: review_result.model_dump(mode="json"),
            CRITERIA_FIELD: INVESTMENT_DOCUMENT_REVIEW_REFLECTION_CRITERIA,
            MAX_ROUNDS_FIELD: DEFAULT_REFLECTION_MAX_ROUNDS,
        }

        if state.todo_plan is not None and state.todo_results:
            from investory.agent_core.runtime.flow.investment_document_review.document_review_todo.summary import (
                build_review_todo_summary,
            )
            review_summary = build_review_todo_summary(
                todo_plan=state.todo_plan,
                completed_results=state.todo_results,
            )
            payload.update(
                {
                    TODO_PLAN_FIELD: state.todo_plan.model_dump(),
                    TODO_RESULTS_FIELD: [
                        result.model_dump() for result in state.todo_results
                    ],
                    REVIEW_SUMMARY_FIELD: review_summary.model_dump(),
                }
            )

        return InvestmentDocumentReviewReflectionInput.model_validate(
            payload
        ).model_dump(exclude_none=True)

    def _build_review_risk_assessment_payload(
        self,
        *,
        state: InvestmentDocumentReviewState,
    ) -> dict[str, Any]:
        if state.document_type is None:
            raise RuntimeError("Document review flow has no classified document type.")

        if state.output is None or not state.output.ok:
            raise RuntimeError("Document review flow has no successful review result.")

        review_result = InvestmentDocumentReviewResult.model_validate(
            state.output.result
        )

        task_status_summary: list[str]
        if state.todo_plan is not None and state.todo_results:
            from investory.agent_core.runtime.flow.investment_document_review.document_review_todo.summary import (
                build_review_todo_summary,
                build_review_task_status_summary,
            )
            review_summary = build_review_todo_summary(
                todo_plan=state.todo_plan,
                completed_results=state.todo_results,
            )
            task_status_summary = build_review_task_status_summary(
                review_summary=review_summary
            )
        else:
            task_status_summary = _build_review_task_status_summary(
                review_result=review_result
            )

        return InvestmentDocumentReviewRiskAssessmentInput.model_validate(
            {
                DOCUMENT_TYPE_FIELD: state.document_type,
                ROUTE_CONFIDENCE_FIELD: state.route_confidence or 0.0,
                "risk_findings": review_result.risk_findings,
                "information_gaps": review_result.information_gaps,
                "boundary_notes": review_result.boundary_notes,
                "task_status_summary": task_status_summary,
            }
        ).model_dump()