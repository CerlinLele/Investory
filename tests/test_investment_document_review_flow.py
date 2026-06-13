from datetime import datetime, timezone
import logging
from threading import Lock
from time import perf_counter, sleep

import investory.agent_core.runtime.flow.investment_document_review.document_review_flow as document_review_flow_module
from investory.agent_core.contracts.investment_document_review_state import (
    ANALYZE_FOCUS_FIELD,
    DOCUMENT_TEXT_FIELD,
    DOCUMENT_TYPE_HINT_FIELD,
    EXTRACT_FOCUS_FIELD,
    REVIEW_GOAL_FIELD,
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
    AGGREGATE_ANALYZE_TASK_ID,
    ACTION_FIELD,
    CHUNK_REVIEW_SCOPE,
    CHUNK_COUNT_FIELD,
    CHUNK_EXTRACT_TASK_ID_PREFIX,
    CHUNK_INDEX_FIELD,
    CHUNK_REVIEW_SCOPE_FIELD,
    DOCUMENT_TYPE_FIELD,
    FULL_DOCUMENT_REVIEW_SCOPE,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    APPROVAL_FIELD,
    PENDING_APPROVAL_ROUTE,
    REVIEW_FIELD,
    REQUIRED_ROLE_FIELD,
    RISK_ASSESSMENT_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    STATUS_FIELD,
    SYNTHESIZE_REVIEW_TASK_ID,
    InvestmentDocumentReviewAction,
    InvestmentDocumentReviewFlow,
    should_use_chunk_review,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    get_review_framework,
)
from investory.agent_core.task_models.investment_document_review import (
    COMPLIANCE_REVIEWER_ROLE,
    InvestmentDocumentReviewApprovalStatus,
    InvestmentDocumentReviewRiskLevel,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)


def _review_result(
    *,
    document_type: InvestmentDocumentType = InvestmentDocumentType.ETF_FACTSHEET,
    extracted_facts: list[str] | None = None,
    risk_findings: list[str] | None = None,
    information_gaps: list[str] | None = None,
    boundary_notes: list[str] | None = None,
    summary: str = "The review is grounded in the provided document.",
) -> dict:
    return {
        "document_type": document_type.value,
        "extracted_facts": extracted_facts or ["Management fee is 0.10%."],
        "risk_findings": risk_findings or ["Fee disclosure is present."],
        "information_gaps": information_gaps or [],
        "boundary_notes": boundary_notes or [
            "This review does not provide investment advice."
        ],
        "summary": summary,
    }


def _reflection_result(review_result: dict) -> dict:
    return {
        "review_result": review_result,
        "passed": True,
        "score": 0.95,
        "issues": [],
        "suggestions": [],
        "safety_flags": [],
        "rounds": 1,
    }


class FakeExecutor:
    def __init__(self, result: TaskResult | None = None) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec.name, payload))
        if self.result is None and spec.name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name:
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result={
                    "overall_risk": InvestmentDocumentReviewRiskLevel.LOW.value,
                    "risk_reason": "Structured review findings do not block automatic release.",
                    "critical_issues": [],
                    "approval_status": (
                        InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                    ),
                    "required_role": None,
                    "auto_proceed": True,
                },
            )
        if self.result is None and spec.name == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name:
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result=_reflection_result(payload["review_result"]),
            )
        if self.result is None and spec.name in {
            INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
            INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
        }:
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result=_review_result(summary=f"Handled by {spec.name}."),
            )
        return self.result or TaskResult(
            ok=True,
            task_name=spec.name,
            result={"handled_by": spec.name},
        )


class DocumentTypePlanExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec.name, payload))
        task_suffix = payload[DOCUMENT_TYPE_FIELD].value
        extract_task_id = f"extract_{task_suffix}"
        analyze_task_id = f"analyze_{task_suffix}"
        return TaskResult(
            ok=True,
            task_name=spec.name,
            result={
                "tasks": [
                    {
                        "id": extract_task_id,
                        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                        "title": "Extract document facts",
                        "description": "Extract document-grounded facts for review.",
                        "payload": {
                            EXTRACT_FOCUS_FIELD: payload[EXTRACT_FOCUS_FIELD],
                        },
                        "depends_on": [],
                        "completion_criteria": [
                            "Extracted facts include source-grounded details."
                        ],
                    },
                    {
                        "id": analyze_task_id,
                        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                        "title": "Analyze extracted facts",
                        "description": "Analyze risks and gaps from extracted facts.",
                        "payload": {
                            ANALYZE_FOCUS_FIELD: payload[ANALYZE_FOCUS_FIELD],
                        },
                        "depends_on": [extract_task_id],
                        "completion_criteria": [
                            "Findings cite the upstream extraction task."
                        ],
                    },
                ],
                "summary": "Extract document facts before analyzing risks and gaps.",
            },
        )


class FakeDocumentReviewRouter:
    def __init__(self, decision: InvestmentDocumentReviewRouteDecision) -> None:
        self.decision = decision
        self.calls: list[dict] = []

    def route(self, payload: dict) -> InvestmentDocumentReviewRouteDecision:
        self.calls.append(payload)
        return self.decision


class RecordingTodoRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[TodoExecutionPlan, TodoExecutionResumeState | None]] = []

    async def run(
        self,
        plan: TodoExecutionPlan,
        *,
        resume_state: TodoExecutionResumeState | None = None,
    ) -> list[TodoTaskResult]:
        self.calls.append((plan, resume_state))
        return [
            TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.SUCCEEDED,
                result={"handled_by": "recording_runner", "task_kind": task.kind.value},
            )
            for task in plan.tasks
        ]


class RecordingTodoResumeStore:
    def __init__(
        self,
        resume_state: TodoExecutionResumeState | None = None,
    ) -> None:
        self.resume_state = resume_state
        self.load_calls: list[tuple[str, TodoExecutionPlan]] = []
        self.save_calls: list[
            tuple[
                str,
                TodoExecutionPlan,
                list[TodoTaskResult],
                TodoExecutionResumeState | None,
            ]
        ] = []

    def load_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
    ) -> TodoExecutionResumeState | None:
        self.load_calls.append((session_id, plan))
        return self.resume_state

    def save_resume_state(
        self,
        *,
        session_id: str,
        plan: TodoExecutionPlan,
        results: list[TodoTaskResult],
        previous_resume_state: TodoExecutionResumeState | None,
    ) -> None:
        self.save_calls.append((session_id, plan, results, previous_resume_state))


class RunnerBackedReviewFlow(InvestmentDocumentReviewFlow):
    def __init__(
        self,
        runner: RecordingTodoRunner,
        *,
        todo_resume_store: RecordingTodoResumeStore | None = None,
    ) -> None:
        self.todo_runner = runner
        super().__init__(
            executor=FakeExecutor(),
            llm_router=FakeDocumentReviewRouter(
                InvestmentDocumentReviewRouteDecision(
                    document_type=InvestmentDocumentType.ETF_FACTSHEET,
                    confidence=0.91,
                    reason="unused",
                )
            ),
            todo_resume_store=todo_resume_store,
        )

    def _build_todo_execution_runner(self, state, *, resume_state=None):
        return self.todo_runner


def test_document_review_flow_returns_missing_input_for_missing_document_text() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.9,
            reason="unused",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run({REVIEW_GOAL_FIELD: "Check fees"})

    assert result.ok is True
    assert result.task_name == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert result.result is not None
    assert (
        result.result[ACTION_FIELD]
        == InvestmentDocumentReviewAction.ASK_FOR_MISSING_INPUT.value
    )
    assert result.result[MISSING_FIELDS_FIELD] == [DOCUMENT_TEXT_FIELD]
    assert router.calls == []
    assert executor.calls == []


def test_document_review_flow_refuses_investment_advice_request() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.9,
            reason="unused",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: "This factsheet describes fees and holdings.",
            REVIEW_GOAL_FIELD: "Should I buy this ETF now?",
        }
    )

    assert result.ok is True
    assert result.result is not None
    assert (
        result.result[ACTION_FIELD]
        == InvestmentDocumentReviewAction.REFUSE_AND_REDIRECT.value
    )
    assert MESSAGE_FIELD in result.result
    assert router.calls == []
    assert executor.calls == []


def test_document_review_flow_refuses_realtime_request_without_capability() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.9,
            reason="unused",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: "This factsheet describes fees and holdings.",
            REVIEW_GOAL_FIELD: "What is today's price and latest move?",
        }
    )

    assert result.ok is True
    assert result.result is not None
    assert (
        result.result[ACTION_FIELD]
        == InvestmentDocumentReviewAction.REFUSE_AND_REDIRECT.value
    )
    assert router.calls == []
    assert executor.calls == []


def test_document_review_flow_returns_missing_input_for_unknown_document_type() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.UNKNOWN,
            confidence=0.43,
            reason="The excerpt is too weak to classify safely.",
            missing_fields=[DOCUMENT_TYPE_HINT_FIELD],
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run({DOCUMENT_TEXT_FIELD: "Short unclear document snippet."})

    assert result.ok is True
    assert result.result is not None
    assert (
        result.result[ACTION_FIELD]
        == InvestmentDocumentReviewAction.ASK_FOR_MISSING_INPUT.value
    )
    assert result.result[MISSING_FIELDS_FIELD] == [DOCUMENT_TYPE_HINT_FIELD]
    assert len(router.calls) == 1
    assert executor.calls == []


def test_document_review_flow_executes_known_document_review_task() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    payload = {
        DOCUMENT_TEXT_FIELD: "The ETF tracks the S&P 500 and charges 0.03%.",
        REVIEW_GOAL_FIELD: "Check major fees and risks",
    }
    result = flow.run(payload)

    framework = get_review_framework(InvestmentDocumentType.ETF_FACTSHEET)

    assert result.ok is True
    assert result.task_name == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == InvestmentDocumentReviewAction.COMPLETE.value
    assert (
        result.result[DOCUMENT_TYPE_FIELD]
        == InvestmentDocumentType.ETF_FACTSHEET.value
    )
    assert (
        result.result[ROUTE_REASON_FIELD]
        == "The excerpt clearly matches an ETF factsheet."
    )
    assert result.result[ROUTE_CONFIDENCE_FIELD] == 0.91
    assert result.result[REVIEW_FIELD]["summary"] == (
        f"Handled by {INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name}."
    )
    assert [name for name, _ in executor.calls] == [
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
    ]
    assert executor.calls[0][1] == {
        DOCUMENT_TEXT_FIELD: payload[DOCUMENT_TEXT_FIELD],
        DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
        EXTRACT_FOCUS_FIELD: framework.extract_focus if framework else [],
        ANALYZE_FOCUS_FIELD: framework.analyze_focus if framework else [],
        REVIEW_GOAL_FIELD: payload[REVIEW_GOAL_FIELD],
    }
    assert executor.calls[1][1]["review_result"]["summary"] == (
        f"Handled by {INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name}."
    )
    assert executor.calls[2][1] == {
        DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
        ROUTE_CONFIDENCE_FIELD: 0.91,
        "risk_findings": ["Fee disclosure is present."],
        "information_gaps": [],
        "boundary_notes": ["This review does not provide investment advice."],
        "task_status_summary": [
            (
                "single_pass_review | succeeded | "
                f"Handled by {INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name}."
            )
        ],
    }


def test_document_review_flow_keeps_medium_risk_single_pass_reviews_complete() -> None:
    class MediumRiskExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                        "extracted_facts": ["Management fee is 0.03%."],
                        "risk_findings": ["Fee disclosure is concise but not dated."],
                        "information_gaps": ["No source date is shown for the fee table."],
                        "boundary_notes": [
                            "The review does not assess live market conditions."
                        ],
                        "summary": "The factsheet discloses a 0.03% management fee.",
                    },
                )
            if spec.name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "overall_risk": InvestmentDocumentReviewRiskLevel.MEDIUM.value,
                        "risk_reason": "A minor disclosure gap exists but does not block release.",
                        "critical_issues": [],
                        "approval_status": (
                            InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                        ),
                        "required_role": None,
                        "auto_proceed": True,
                    },
                )
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result=_reflection_result(payload["review_result"]),
                )
            raise AssertionError(f"Unexpected task {spec.name}")

    executor = MediumRiskExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: "The ETF tracks the S&P 500 and charges 0.03%.",
            REVIEW_GOAL_FIELD: "Check major fees and risks",
        }
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result[ACTION_FIELD] == InvestmentDocumentReviewAction.COMPLETE.value
    assert result.result[REVIEW_FIELD]["summary"] == (
        "The factsheet discloses a 0.03% management fee."
    )
    assert result.result[RISK_ASSESSMENT_FIELD] == {
        "overall_risk": InvestmentDocumentReviewRiskLevel.MEDIUM.value,
        "risk_reason": "A minor disclosure gap exists but does not block release.",
        "critical_issues": [],
        "approval_status": (
            InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
        ),
        "required_role": None,
        "auto_proceed": True,
    }
    assert result.result[APPROVAL_FIELD] == {
        STATUS_FIELD: InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value,
        REQUIRED_ROLE_FIELD: None,
    }
    assert [name for name, _ in executor.calls] == [
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
    ]


def test_document_review_flow_routes_only_multi_chunk_documents_to_chunk_review() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    single_chunk_state = InvestmentDocumentReviewState(
        input_payload={},
        document_chunks=["short excerpt"],
    )
    multi_chunk_state = InvestmentDocumentReviewState(
        input_payload={},
        document_chunks=["first chunk", "second chunk"]
    )

    assert should_use_chunk_review(single_chunk_state) is False
    assert flow.route_after_review_framework(single_chunk_state) == FULL_DOCUMENT_REVIEW_SCOPE
    assert should_use_chunk_review(multi_chunk_state) is True
    assert flow.route_after_review_framework(multi_chunk_state) == CHUNK_REVIEW_SCOPE


def test_document_review_flow_uses_chunk_todo_path_for_multi_chunk_document() -> None:
    executor = FakeExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    long_document = "\n\n".join(
        [
            (
                f"Section {idx}: The ETF factsheet describes fees, holdings, "
                "index exposure, risk disclosures, performance limits, and "
                "important investor notices. "
            )
            * 3
            for idx in range(8)
        ]
    )

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: long_document,
            REVIEW_GOAL_FIELD: "Check major fees and risks",
        }
    )

    assert result.ok is True
    assert result.task_name == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert result.result is not None
    assert result.result[ACTION_FIELD] == InvestmentDocumentReviewAction.COMPLETE.value
    assert result.result[REVIEW_FIELD]["summary"] == (
        f"Handled by {INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name}."
    )
    called_task_names = [call[0] for call in executor.calls]
    assert called_task_names.count(INVESTMENT_DOCUMENT_EXTRACT_TASK.name) > 1
    assert INVESTMENT_DOCUMENT_ANALYZE_TASK.name in called_task_names
    assert called_task_names[-3:] == [
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
    ]


def test_document_review_flow_keeps_medium_risk_chunk_reviews_complete() -> None:
    class MediumRiskChunkExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            if spec.name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "overall_risk": InvestmentDocumentReviewRiskLevel.MEDIUM.value,
                        "risk_reason": "The chunk review found limited disclosure gaps only.",
                        "critical_issues": [],
                        "approval_status": (
                            InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                        ),
                        "required_role": None,
                        "auto_proceed": True,
                    },
                )
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result=_reflection_result(payload["review_result"]),
                )
            if spec.name == INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result=_review_result(summary=f"Handled by {spec.name}."),
                )
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result={"handled_by": spec.name},
            )

    executor = MediumRiskChunkExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    long_document = "\n\n".join(
        [
            (
                f"Section {idx}: The ETF factsheet describes fees, holdings, "
                "index exposure, risk disclosures, performance limits, and "
                "important investor notices. "
            )
            * 3
            for idx in range(8)
        ]
    )

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: long_document,
            REVIEW_GOAL_FIELD: "Check major fees and risks",
        }
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result[ACTION_FIELD] == InvestmentDocumentReviewAction.COMPLETE.value
    assert result.result[REVIEW_FIELD]["summary"] == (
        f"Handled by {INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name}."
    )
    assert result.result[RISK_ASSESSMENT_FIELD]["overall_risk"] == (
        InvestmentDocumentReviewRiskLevel.MEDIUM.value
    )
    assert result.result[APPROVAL_FIELD] == {
        STATUS_FIELD: InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value,
        REQUIRED_ROLE_FIELD: None,
    }
    assert [name for name, _ in executor.calls][-3:] == [
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name,
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
    ]


def test_document_review_flow_routes_high_risk_reviews_to_pending_human_approval() -> None:
    class HighRiskExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                        "extracted_facts": ["Management fee is 0.03%."],
                        "risk_findings": ["Benchmark methodology is not disclosed."],
                        "information_gaps": ["No benchmark methodology is provided."],
                        "boundary_notes": [
                            "The review does not assess live market conditions."
                        ],
                        "summary": "The factsheet omits benchmark methodology details.",
                    },
                )
            if spec.name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
                        "risk_reason": "A material disclosure gap requires manual approval.",
                        "critical_issues": ["No benchmark methodology is provided."],
                        "approval_status": (
                            InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                        ),
                        "required_role": COMPLIANCE_REVIEWER_ROLE,
                        "auto_proceed": False,
                    },
                )
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result=_reflection_result(payload["review_result"]),
                )
            raise AssertionError(f"Unexpected task {spec.name}")

    executor = HighRiskExecutor()
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: "The ETF factsheet lists fees but omits benchmark details.",
            REVIEW_GOAL_FIELD: "Check major fees and risks",
        }
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result[ACTION_FIELD] == (
        InvestmentDocumentReviewAction.PENDING_HUMAN_APPROVAL.value
    )
    assert result.result[REVIEW_FIELD]["summary"] == (
        "The factsheet omits benchmark methodology details."
    )
    assert result.result[RISK_ASSESSMENT_FIELD] == {
        "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
        "risk_reason": "A material disclosure gap requires manual approval.",
        "critical_issues": ["No benchmark methodology is provided."],
        "approval_status": (
            InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
        ),
        "required_role": COMPLIANCE_REVIEWER_ROLE,
        "auto_proceed": False,
    }
    assert result.result[APPROVAL_FIELD] == {
        STATUS_FIELD: (
            InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
        ),
        REQUIRED_ROLE_FIELD: COMPLIANCE_REVIEWER_ROLE,
    }


def test_generate_review_todo_plan_node_builds_plan_without_executing_tasks() -> None:
    plan_payload = {
        "tasks": [
            {
                "id": "extract_fees",
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                "title": "Extract fees",
                "description": "Extract fee facts from the document.",
                "payload": {"extract_focus": ["fees"]},
                "depends_on": [],
                "completion_criteria": ["Fees are listed with source citations."],
            },
            {
                "id": "analyze_fee_disclosure",
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "title": "Analyze fee disclosure",
                "description": "Assess fee disclosure from extracted facts.",
                "payload": {"analyze_focus": ["fee disclosure"]},
                "depends_on": ["extract_fees"],
                "completion_criteria": ["Findings cite upstream facts."],
            },
        ],
        "summary": "Extract fee facts before assessing disclosure quality.",
    }
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
            result=plan_payload,
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    review_payload = {
        DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% fee.",
        DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
        EXTRACT_FOCUS_FIELD: ["fees"],
        ANALYZE_FOCUS_FIELD: ["fee disclosure"],
        REVIEW_GOAL_FIELD: "Review fee disclosure",
        "unexpected_field": "not part of plan input",
    }

    update = flow.generate_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: review_payload[DOCUMENT_TEXT_FIELD]},
            review_payload=review_payload,
        )
    )

    assert update["todo_plan"] == TodoExecutionPlan.model_validate(plan_payload)
    assert "output" not in update
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
            {
                DOCUMENT_TEXT_FIELD: review_payload[DOCUMENT_TEXT_FIELD],
                DOCUMENT_TYPE_FIELD: review_payload[DOCUMENT_TYPE_FIELD],
                EXTRACT_FOCUS_FIELD: review_payload[EXTRACT_FOCUS_FIELD],
                ANALYZE_FOCUS_FIELD: review_payload[ANALYZE_FOCUS_FIELD],
                REVIEW_GOAL_FIELD: review_payload[REVIEW_GOAL_FIELD],
            },
        )
    ]


def test_generate_review_todo_plan_accepts_supported_document_type_frameworks() -> None:
    executor = DocumentTypePlanExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    document_types = (
        InvestmentDocumentType.ETF_FACTSHEET,
        InvestmentDocumentType.FUND_PROSPECTUS,
    )

    for document_type in document_types:
        input_payload = {
            DOCUMENT_TEXT_FIELD: f"{document_type.value} review excerpt.",
            REVIEW_GOAL_FIELD: "Review major risks and information gaps.",
        }
        framework_update = flow.build_review_framework(
            InvestmentDocumentReviewState(
                input_payload=input_payload,
                document_type=document_type,
            )
        )
        update = flow.generate_review_todo_plan(
            InvestmentDocumentReviewState(
                input_payload=input_payload,
                document_type=document_type,
                review_payload=framework_update["review_payload"],
            )
        )

        assert "output" not in update
        todo_plan = update["todo_plan"]
        assert len(todo_plan.tasks) == 2
        assert todo_plan.tasks[0].depends_on == []
        assert todo_plan.tasks[1].depends_on == [todo_plan.tasks[0].id]

        framework = get_review_framework(document_type)
        assert framework is not None
        latest_payload = executor.calls[-1][1]
        assert latest_payload[DOCUMENT_TYPE_FIELD] == document_type
        assert latest_payload[EXTRACT_FOCUS_FIELD] == framework.extract_focus
        assert latest_payload[ANALYZE_FOCUS_FIELD] == framework.analyze_focus

    assert [call[0] for call in executor.calls] == [
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
    ]


def test_generate_review_todo_plan_builds_dimension_analyze_fan_out_for_multi_chunk_documents() -> None:
    executor = FakeExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    update = flow.generate_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt.",
                REVIEW_GOAL_FIELD: "Review fees, holdings, and risk gaps.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            review_payload={
                DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt.",
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                EXTRACT_FOCUS_FIELD: ["fees", "holdings", "risks"],
                ANALYZE_FOCUS_FIELD: [
                    "Fee Disclosure",
                    "Holdings / Concentration",
                    "Fee disclosure ",
                ],
                REVIEW_GOAL_FIELD: "Review fees, holdings, and risk gaps.",
            },
            document_chunks=["chunk 1", "chunk 2", "chunk 3"],
        )
    )

    todo_plan = update["todo_plan"]
    extract_tasks = todo_plan.tasks[:3]
    analyze_tasks = todo_plan.tasks[3:6]
    synthesize_task = todo_plan.tasks[6]

    extract_task_ids = [
        f"{CHUNK_EXTRACT_TASK_ID_PREFIX}_{idx:04d}" for idx in range(1, 4)
    ]
    assert [task.id for task in extract_tasks] == extract_task_ids
    assert all(task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT for task in extract_tasks)
    assert [task.depends_on for task in extract_tasks] == [[], [], []]
    assert [task.payload[CHUNK_INDEX_FIELD] for task in extract_tasks] == [0, 1, 2]
    assert [task.payload[CHUNK_COUNT_FIELD] for task in extract_tasks] == [3, 3, 3]
    assert [task.payload[CHUNK_REVIEW_SCOPE_FIELD] for task in extract_tasks] == [
        CHUNK_REVIEW_SCOPE,
        CHUNK_REVIEW_SCOPE,
        CHUNK_REVIEW_SCOPE,
    ]

    assert [task.id for task in analyze_tasks] == [
        "analyze_fee_disclosure",
        "analyze_holdings_concentration",
        "analyze_fee_disclosure_2",
    ]
    assert all(task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE for task in analyze_tasks)
    assert [task.payload[ANALYZE_FOCUS_FIELD] for task in analyze_tasks] == [
        ["Fee Disclosure"],
        ["Holdings / Concentration"],
        ["Fee disclosure"],
    ]
    assert all(task.depends_on == extract_task_ids for task in analyze_tasks)

    assert synthesize_task.id == SYNTHESIZE_REVIEW_TASK_ID
    assert synthesize_task.kind == TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE
    assert synthesize_task.depends_on == [task.id for task in analyze_tasks]
    assert (
        todo_plan.summary
        == "Extract lightweight evidence from every document chunk, analyze the "
        "evidence by review dimension, then synthesize the full document review."
    )
    assert executor.calls == []


def test_generate_review_todo_plan_uses_fallback_analyze_task_when_no_dimension_focus_survives_cleaning() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    update = flow.generate_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            review_payload={
                DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt.",
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                EXTRACT_FOCUS_FIELD: ["fees"],
                ANALYZE_FOCUS_FIELD: [" ", "", "   "],
                REVIEW_GOAL_FIELD: "Review fees.",
            },
            document_chunks=["chunk 1", "chunk 2"],
        )
    )

    todo_plan = update["todo_plan"]

    assert [task.id for task in todo_plan.tasks] == [
        "extract_chunk_0001",
        "extract_chunk_0002",
        AGGREGATE_ANALYZE_TASK_ID,
        SYNTHESIZE_REVIEW_TASK_ID,
    ]
    assert todo_plan.tasks[2].kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE
    assert todo_plan.tasks[2].payload[ANALYZE_FOCUS_FIELD] == []
    assert todo_plan.tasks[2].depends_on == [
        "extract_chunk_0001",
        "extract_chunk_0002",
    ]
    assert todo_plan.tasks[3].depends_on == [AGGREGATE_ANALYZE_TASK_ID]


def test_generate_review_todo_plan_returns_error_for_invalid_chunk_plan(monkeypatch) -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    monkeypatch.setattr(
        document_review_flow_module,
        "_build_chunk_review_analyze_tasks",
        lambda **_: [
            {
                "id": "analyze_duplicate",
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "title": "Analyze first duplicate",
                "description": "Duplicate analyze task.",
                "payload": {ANALYZE_FOCUS_FIELD: ["fees"]},
                "depends_on": ["extract_chunk_0001", "extract_chunk_0002"],
                "completion_criteria": ["First duplicate."],
            },
            {
                "id": "analyze_duplicate",
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "title": "Analyze second duplicate",
                "description": "Duplicate analyze task.",
                "payload": {ANALYZE_FOCUS_FIELD: ["risks"]},
                "depends_on": ["extract_chunk_0001", "extract_chunk_0002"],
                "completion_criteria": ["Second duplicate."],
            },
        ],
    )

    update = flow.generate_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            review_payload={
                DOCUMENT_TEXT_FIELD: "Chunked ETF factsheet excerpt.",
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                EXTRACT_FOCUS_FIELD: ["fees"],
                ANALYZE_FOCUS_FIELD: ["fees", "risks"],
                REVIEW_GOAL_FIELD: "Review fees and risks.",
            },
            document_chunks=["chunk 1", "chunk 2"],
        )
    )

    assert "todo_plan" not in update
    output = update["output"]
    assert output.ok is False
    assert output.task_name == INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name
    assert output.error is not None
    assert output.error.error_type == "structured_output_failed"
    assert output.error.stage == "output_validation"
    assert output.error.debug_message is not None
    assert "duplicate_task_id" in output.error.debug_message


def test_generate_review_todo_plan_logs_plan_summary_and_tasks(caplog) -> None:
    executor = DocumentTypePlanExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    input_payload = {
        DOCUMENT_TEXT_FIELD: "ETF factsheet review excerpt.",
        REVIEW_GOAL_FIELD: "Review major risks and information gaps.",
    }

    with caplog.at_level(logging.DEBUG, logger="investory.agent_core.runtime.flow.investment_document_review.document_review_flow"):
        update = flow.generate_review_todo_plan(
            InvestmentDocumentReviewState(
                input_payload=input_payload,
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                review_payload=flow.build_review_framework(
                    InvestmentDocumentReviewState(
                        input_payload=input_payload,
                        document_type=InvestmentDocumentType.ETF_FACTSHEET,
                    )
                )["review_payload"],
                session_id="session-logging-check",
            )
        )

    assert "todo_plan" in update
    assert any(
        "investment_document_review.todo_plan.generated" in record.message
        and "session-logging-check" in record.message
        and "task_count=2" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_plan.task" in record.message
        and "task_id=extract_etf_factsheet" in record.message
        for record in caplog.records
    )
    assert all("ETF factsheet review excerpt." not in record.message for record in caplog.records)


def test_reflect_review_output_records_metadata_and_logs_completion(caplog) -> None:
    class ReflectionMetadataExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result={
                    "review_result": payload["review_result"],
                    "passed": False,
                    "score": 0.72,
                    "issues": ["Skipped task disclosure is incomplete."],
                    "suggestions": ["Add the skipped task to boundary notes."],
                    "safety_flags": ["incomplete_task_disclosure"],
                    "rounds": 1,
                },
            )

    executor = ReflectionMetadataExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    review_result = _review_result(summary="Reflection should preserve this summary.")

    with caplog.at_level(
        logging.INFO,
        logger="investory.agent_core.runtime.flow.investment_document_review.document_review_flow",
    ):
        update = flow.reflect_review_output(
            InvestmentDocumentReviewState(
                session_id="session-reflection-log",
                input_payload={
                    DOCUMENT_TEXT_FIELD: "ETF factsheet text should not be logged.",
                    REVIEW_GOAL_FIELD: "Review missing disclosures.",
                },
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                route_confidence=0.91,
                output=TaskResult(
                    ok=True,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
                    result=review_result,
                ),
            )
        )

    assert executor.calls[0][0] == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name
    assert update["output"] == TaskResult(
        ok=True,
        task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
        result={**review_result, "learning_next_steps": None},
    )
    assert update["reflection_passed"] is False
    assert update["reflection_rounds"] == 1
    assert update["reflection_result"]["score"] == 0.72
    assert update["reflection_result"]["issues"] == [
        "Skipped task disclosure is incomplete."
    ]
    assert any(
        "investment_document_review.reflection.started" in record.message
        and "session-reflection-log" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.reflection.completed" in record.message
        and "session-reflection-log" in record.message
        and "passed=false" in record.message
        and "score=0.72" in record.message
        and "rounds=1" in record.message
        and "issue_count=1" in record.message
        and "safety_flag_count=1" in record.message
        for record in caplog.records
    )
    assert all(
        "ETF factsheet text should not be logged." not in record.message
        for record in caplog.records
    )


def test_reflect_review_output_logs_failed_reflection_task(caplog) -> None:
    class FailedReflectionExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            return TaskResult(
                ok=False,
                task_name=spec.name,
                    error=TaskError(
                        error_type="unknown_error",
                        stage="model_call",
                        user_safe_message="Reflection could not complete.",
                    ),
                )

    executor = FailedReflectionExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    with caplog.at_level(
        logging.INFO,
        logger="investory.agent_core.runtime.flow.investment_document_review.document_review_flow",
    ):
        update = flow.reflect_review_output(
            InvestmentDocumentReviewState(
                session_id="session-reflection-failed",
                input_payload={DOCUMENT_TEXT_FIELD: "Failure text should not leak."},
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                route_confidence=0.91,
                output=TaskResult(
                    ok=True,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
                    result=_review_result(),
                ),
            )
        )

    assert update["output"].ok is False
    assert update["output"].task_name == INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name
    assert update["output"].error is not None
    assert update["output"].error.error_type == "unknown_error"
    assert any(
        "investment_document_review.reflection.started" in record.message
        and "session-reflection-failed" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.reflection.failed" in record.message
        and "session-reflection-failed" in record.message
        and "stage=model_call" in record.message
        and "error_type=unknown_error" in record.message
        for record in caplog.records
    )
    assert all(
        "Failure text should not leak." not in record.message
        for record in caplog.records
    )


def test_generate_review_todo_plan_requires_review_payload() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    try:
        flow.generate_review_todo_plan(
            InvestmentDocumentReviewState(
                input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."}
            )
        )
    except RuntimeError as exc:
        assert str(exc) == "Document review flow has no review payload to plan."
    else:
        raise AssertionError("Expected missing review payload to raise RuntimeError.")


def test_generate_review_todo_plan_returns_error_for_invalid_plan() -> None:
    invalid_plan_payload = {
        "tasks": [
            {
                "id": "analyze_fee_disclosure",
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "title": "Analyze fee disclosure",
                "description": "Assess fee disclosure from extracted facts.",
                "payload": {"analyze_focus": ["fee disclosure"]},
                "depends_on": ["extract_fees"],
                "completion_criteria": ["Findings cite upstream facts."],
            },
        ],
        "summary": "Invalid plan with a missing dependency.",
    }
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
            result=invalid_plan_payload,
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    update = flow.generate_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            review_payload={
                DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt.",
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                EXTRACT_FOCUS_FIELD: ["fees"],
                ANALYZE_FOCUS_FIELD: ["fee disclosure"],
                REVIEW_GOAL_FIELD: None,
            },
        )
    )

    assert "todo_plan" not in update
    output = update["output"]
    assert output.ok is False
    assert output.task_name == INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name
    assert output.error is not None
    assert output.error.error_type == "structured_output_failed"
    assert output.error.stage == "output_validation"
    assert output.error.debug_message is not None
    assert "unknown_dependency" in output.error.debug_message


def test_execute_review_todo_plan_uses_todo_execution_runner() -> None:
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract fee facts before assessing disclosure quality.",
        }
    )
    runner = RecordingTodoRunner()
    flow = RunnerBackedReviewFlow(runner)

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            todo_plan=todo_plan,
        )
    )

    assert runner.calls == [(todo_plan, None)]
    assert update["todo_results"] == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "handled_by": "recording_runner",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT.value,
            },
        ),
        TodoTaskResult(
            id="analyze_fee_disclosure",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "handled_by": "recording_runner",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE.value,
            },
        ),
    ]


def test_execute_review_todo_plan_logs_runner_lifecycle(caplog) -> None:
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract fee facts before assessing disclosure quality.",
        }
    )
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    with caplog.at_level(
        logging.DEBUG,
        logger="investory.agent_core.runtime.flow.investment_document_review.document_review_flow",
    ):
        update = flow.execute_review_todo_plan(
            InvestmentDocumentReviewState(
                session_id="session-lifecycle-log",
                input_payload={
                    DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt.",
                    REVIEW_GOAL_FIELD: "Review major risks and information gaps.",
                },
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                todo_plan=todo_plan,
            )
        )

    assert len(update["todo_results"]) == 2
    assert any(
        "investment_document_review.todo_execution.started" in record.message
        and "session-lifecycle-log" in record.message
        and "task_count=2" in record.message
        and "resume_task_count=0" in record.message
        and "failure_policy=retry_then_fail" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_execution.completed" in record.message
        and "session-lifecycle-log" in record.message
        and "succeeded_count=2" in record.message
        and "failed_count=0" in record.message
        and "skipped_count=0" in record.message
        and "synthesis_produced=false" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_layer.started" in record.message
        and "session-lifecycle-log" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_task.started" in record.message
        and "task_id=extract_fees" in record.message
        and "session-lifecycle-log" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_task.succeeded" in record.message
        and "task_id=analyze_fee_disclosure" in record.message
        for record in caplog.records
    )
    assert all("ETF factsheet excerpt." not in record.message for record in caplog.records)


def test_execute_review_todo_plan_loads_and_saves_resume_state_slot(caplog) -> None:
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                }
            ],
            "summary": "Extract fee facts.",
        }
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        session_id="session-1",
        plan=todo_plan,
        results_by_id={
            "extract_fees": TodoTaskResult(
                id="extract_fees",
                status=TodoTaskStatus.SUCCEEDED,
                result={"summary": "Fee facts extracted in a previous run."},
            )
        },
        attempts_by_id={"extract_fees": 1},
        updated_at=datetime(2026, 6, 7, 7, 0, tzinfo=timezone.utc),
    )
    resume_store = RecordingTodoResumeStore(resume_state=resume_state)
    runner = RecordingTodoRunner()
    flow = RunnerBackedReviewFlow(
        runner,
        todo_resume_store=resume_store,
    )

    with caplog.at_level(
        logging.INFO,
        logger="investory.agent_core.runtime.flow.investment_document_review.document_review_flow",
    ):
        update = flow.execute_review_todo_plan(
            InvestmentDocumentReviewState(
                session_id="session-1",
                input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
                todo_plan=todo_plan,
            )
        )

    expected_results = [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "handled_by": "recording_runner",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT.value,
            },
        )
    ]
    assert runner.calls == [(todo_plan, resume_state)]
    assert resume_store.load_calls == [("session-1", todo_plan)]
    assert resume_store.save_calls == [
        ("session-1", todo_plan, expected_results, resume_state)
    ]
    assert update["todo_results"] == expected_results
    assert any(
        "investment_document_review.todo_resume.loaded" in record.message
        and "session-1" in record.message
        and "resumed_result_count=1" in record.message
        and "attempt_count=1" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_execution.started" in record.message
        and "session-1" in record.message
        and "task_count=1" in record.message
        and "resume_task_count=1" in record.message
        for record in caplog.records
    )
    assert any(
        "investment_document_review.todo_resume.saved" in record.message
        and "session-1" in record.message
        and "saved_result_count=1" in record.message
        for record in caplog.records
    )


def test_execute_review_todo_plan_includes_resumed_completed_results_in_synthesis_once() -> None:
    resume_state = TodoExecutionResumeState(
        run_id="review-run-2",
        session_id="session-2",
        plan=TodoExecutionPlan.model_validate(
            {
                "tasks": [
                    {
                        "id": "extract_fees",
                        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                        "title": "Extract fees",
                        "description": "Extract fee facts from the document.",
                        "payload": {"extract_focus": ["fees"]},
                        "depends_on": [],
                        "completion_criteria": [
                            "Fees are listed with source citations."
                        ],
                    },
                    {
                        "id": "synthesize_review",
                        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                        "title": "Synthesize review",
                        "description": "Combine completed task results into the final review.",
                        "payload": {},
                        "depends_on": ["extract_fees"],
                        "completion_criteria": [
                            "Final review summarizes completed work."
                        ],
                    },
                ],
                "summary": "Resume completed extraction before synthesis.",
            }
        ),
        results_by_id={
            "extract_fees": TodoTaskResult(
                id="extract_fees",
                status=TodoTaskStatus.SUCCEEDED,
                result={
                    "extracted_facts": ["Management fee is 0.10%."],
                    "information_gaps": ["No source date found."],
                    "boundary_notes": ["Facts are limited to the supplied excerpt."],
                    "summary": "Fee facts extracted.",
                },
            )
        },
        attempts_by_id={"extract_fees": 1},
        updated_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
    )
    resume_store = RecordingTodoResumeStore(resume_state=resume_state)
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            result={
                "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                "extracted_facts": ["Management fee is 0.10%."],
                "risk_findings": [],
                "information_gaps": ["No source date found."],
                "boundary_notes": ["Facts are limited to the supplied excerpt."],
                "summary": "The factsheet discloses a 0.10% management fee.",
                "learning_next_steps": [],
            },
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
        todo_resume_store=resume_store,
    )
    todo_plan = resume_state.plan

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            session_id="session-2",
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Summarize completed review work.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="ETF factsheet",
            route_confidence=0.91,
            todo_plan=todo_plan,
        )
    )

    resumed_extract_result = resume_state.results_by_id["extract_fees"]
    assert update["todo_results"] == [
        resumed_extract_result,
        TodoTaskResult(
            id="synthesize_review",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                "extracted_facts": ["Management fee is 0.10%."],
                "risk_findings": [],
                "information_gaps": ["No source date found."],
                "boundary_notes": ["Facts are limited to the supplied excerpt."],
                "summary": "The factsheet discloses a 0.10% management fee.",
                "learning_next_steps": [],
            },
        ),
    ]
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            {
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                ROUTE_REASON_FIELD: "ETF factsheet",
                ROUTE_CONFIDENCE_FIELD: 0.91,
                REVIEW_GOAL_FIELD: "Summarize completed review work.",
                "todo_plan": todo_plan.model_dump(),
                "todo_results": [resumed_extract_result.model_dump()],
                "review_summary": {
                    "plan_summary": "Resume completed extraction before synthesis.",
                    "planned_task_count": 2,
                    "completed_task_count": 1,
                    "succeeded_task_ids": ["extract_fees"],
                    "failed_task_ids": [],
                    "skipped_task_ids": [],
                    "extracted_facts": ["Management fee is 0.10%."],
                    "risk_findings": [],
                    "information_gaps": ["No source date found."],
                    "boundary_notes": ["Facts are limited to the supplied excerpt."],
                    "task_summaries": [
                        {
                            "task_id": "extract_fees",
                            "task_title": "Extract fees",
                            "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                            "status": TodoTaskStatus.SUCCEEDED,
                            "summary": "Fee facts extracted.",
                        }
                    ],
                },
            },
        )
    ]


def test_execute_review_todo_plan_requires_todo_plan() -> None:
    runner = RecordingTodoRunner()
    flow = RunnerBackedReviewFlow(runner)

    try:
        flow.execute_review_todo_plan(
            InvestmentDocumentReviewState(
                input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."}
            )
        )
    except RuntimeError as exc:
        assert str(exc) == "Document review flow has no To-Do plan to execute."
    else:
        raise AssertionError("Expected missing To-Do plan to raise RuntimeError.")

    assert runner.calls == []


def test_execute_review_todo_plan_dispatches_extract_tasks_through_executor() -> None:
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name="investment_document_extract",
            result={
                "extracted_facts": ["Management fee is 0.10%."],
                "source_citations": ["Fee table"],
                "information_gaps": [],
                "boundary_notes": [],
                "summary": "Fee facts extracted.",
            },
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                }
            ],
            "summary": "Extract fee facts.",
        }
    )

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Review fee disclosure",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            todo_plan=todo_plan,
        )
    )

    assert update["todo_results"] == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "extracted_facts": ["Management fee is 0.10%."],
                "source_citations": ["Fee table"],
                "information_gaps": [],
                "boundary_notes": [],
                "summary": "Fee facts extracted.",
            },
        )
    ]
    assert executor.calls == [
        (
            "investment_document_extract",
            {
                "task_id": "extract_fees",
                "task_title": "Extract fees",
                "task_description": "Extract fee facts from the document.",
                "completion_criteria": ["Fees are listed with source citations."],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                REVIEW_GOAL_FIELD: "Review fee disclosure",
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                EXTRACT_FOCUS_FIELD: ["fees"],
            },
        )
    ]


def test_execute_review_todo_plan_dispatches_synthesize_tasks_through_executor() -> None:
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            result={
                "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                "extracted_facts": ["Management fee is 0.10%."],
                "risk_findings": ["Fee disclosure is concise but limited."],
                "information_gaps": ["No portfolio turnover disclosure found."],
                "boundary_notes": ["This review does not provide investment advice."],
                "summary": "The factsheet discloses a 0.10% management fee.",
                "learning_next_steps": [],
            },
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "synthesize_review",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                    "title": "Synthesize review",
                    "description": "Combine completed task results into the final review.",
                    "payload": {},
                    "depends_on": [],
                    "completion_criteria": ["Final review summarizes facts, risks, and gaps."],
                }
            ],
            "summary": "Synthesize the completed review tasks.",
        }
    )
    prior_results = [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "extracted_facts": ["Management fee is 0.10%."],
                "source_citations": ["Fee table"],
                "information_gaps": [],
                "boundary_notes": [],
                "summary": "Fee facts extracted.",
            },
        )
    ]

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Summarize the fee disclosure.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="unused",
            route_confidence=0.91,
            todo_plan=todo_plan,
            todo_results=prior_results,
        )
    )

    assert update["todo_results"] == [
        TodoTaskResult(
            id="synthesize_review",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                "extracted_facts": ["Management fee is 0.10%."],
                "risk_findings": ["Fee disclosure is concise but limited."],
                "information_gaps": ["No portfolio turnover disclosure found."],
                "boundary_notes": ["This review does not provide investment advice."],
                "summary": "The factsheet discloses a 0.10% management fee.",
                "learning_next_steps": [],
            },
        )
    ]
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
            {
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                ROUTE_REASON_FIELD: "unused",
                ROUTE_CONFIDENCE_FIELD: 0.91,
                REVIEW_GOAL_FIELD: "Summarize the fee disclosure.",
                "todo_plan": todo_plan.model_dump(),
                "todo_results": [result.model_dump() for result in prior_results],
                "review_summary": {
                    "plan_summary": "Synthesize the completed review tasks.",
                    "planned_task_count": 1,
                    "completed_task_count": 1,
                    "succeeded_task_ids": ["extract_fees"],
                    "failed_task_ids": [],
                    "skipped_task_ids": [],
                    "extracted_facts": ["Management fee is 0.10%."],
                    "risk_findings": [],
                    "information_gaps": [],
                    "boundary_notes": [],
                    "task_summaries": [
                        {
                            "task_id": "extract_fees",
                            "task_title": None,
                            "task_kind": None,
                            "status": TodoTaskStatus.SUCCEEDED,
                            "summary": "Fee facts extracted.",
                        }
                    ],
                },
            },
        )
    ]


def test_build_review_todo_synthesize_payload_uses_only_completed_todo_results() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
                {
                    "id": "analyze_holdings",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze holdings",
                    "description": "Assess holdings from extracted facts.",
                    "payload": {"analyze_focus": ["holdings"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
                {
                    "id": "synthesize_review",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                    "title": "Synthesize review",
                    "description": "Combine completed task results into the final review.",
                    "payload": {},
                    "depends_on": [],
                    "completion_criteria": ["Final review summarizes completed work."],
                }
            ],
            "summary": "Synthesize completed review tasks.",
        }
    )
    succeeded_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "extracted_facts": ["Management fee is 0.10%."],
            "information_gaps": ["No source date found."],
            "boundary_notes": ["Facts are limited to the supplied excerpt."],
            "summary": "Fee facts extracted.",
        },
    )
    failed_result = TodoTaskResult(
        id="analyze_fee_disclosure",
        status=TodoTaskStatus.FAILED,
        error={"message": "Fee disclosure analysis failed."},
    )
    skipped_result = TodoTaskResult(
        id="analyze_holdings",
        status=TodoTaskStatus.SKIPPED,
        error={"message": "Holdings analysis was skipped."},
    )
    running_result = TodoTaskResult(
        id="extract_risk",
        status=TodoTaskStatus.RUNNING,
        result={"summary": "Risk extraction is still running."},
    )
    pending_result = TodoTaskResult(
        id="extract_holdings",
        status=TodoTaskStatus.PENDING,
    )

    payload = flow._build_review_todo_synthesize_payload(
        state=InvestmentDocumentReviewState(
            input_payload={REVIEW_GOAL_FIELD: "Summarize completed review work."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="ETF factsheet",
            route_confidence=0.91,
            todo_plan=todo_plan,
        ),
        executed_results_by_id={
            result.id: result
            for result in [
                succeeded_result,
                failed_result,
                skipped_result,
                running_result,
                pending_result,
            ]
        },
    )

    assert payload["todo_results"] == [
        succeeded_result.model_dump(),
        failed_result.model_dump(),
        skipped_result.model_dump(),
    ]
    assert payload["review_summary"] == {
        "plan_summary": "Synthesize completed review tasks.",
        "planned_task_count": 4,
        "completed_task_count": 3,
        "succeeded_task_ids": ["extract_fees"],
        "failed_task_ids": ["analyze_fee_disclosure"],
        "skipped_task_ids": ["analyze_holdings"],
        "extracted_facts": ["Management fee is 0.10%."],
        "risk_findings": [],
        "information_gaps": [
            "No source date found.",
            (
                "Analyze fee disclosure (analyze_fee_disclosure) did not complete: "
                "Fee disclosure analysis failed."
            ),
        ],
        "boundary_notes": [
            "Facts are limited to the supplied excerpt.",
            "Analyze holdings (analyze_holdings) did not complete: Holdings analysis was skipped.",
        ],
        "task_summaries": [
            {
                "task_id": "extract_fees",
                "task_title": "Extract fees",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                "status": TodoTaskStatus.SUCCEEDED,
                "summary": "Fee facts extracted.",
            },
            {
                "task_id": "analyze_fee_disclosure",
                "task_title": "Analyze fee disclosure",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "status": TodoTaskStatus.FAILED,
                "summary": "Fee disclosure analysis failed.",
            },
            {
                "task_id": "analyze_holdings",
                "task_title": "Analyze holdings",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                "status": TodoTaskStatus.SKIPPED,
                "summary": "Holdings analysis was skipped.",
            },
        ],
    }


def test_build_review_risk_assessment_payload_uses_reflected_review_and_todo_status() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract fees before analysis.",
        }
    )
    extract_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "extracted_facts": ["Management fee is 0.10%."],
            "information_gaps": ["No source date found."],
            "boundary_notes": ["Facts are limited to the supplied excerpt."],
            "summary": "Fee facts extracted.",
        },
    )
    analyze_result = TodoTaskResult(
        id="analyze_fee_disclosure",
        status=TodoTaskStatus.FAILED,
        error={"message": "Fee disclosure analysis failed."},
    )

    payload = flow._build_review_risk_assessment_payload(
        state=InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "This should not be used directly."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_confidence=0.91,
            todo_plan=todo_plan,
            todo_results=[extract_result, analyze_result],
                output=TaskResult(
                    ok=True,
                    task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                    result=_review_result(
                        risk_findings=["Reflected fee disclosure risk."],
                        information_gaps=["Reflected source-date gap."],
                        boundary_notes=["Reflected non-advisory boundary."],
                        summary="Reflection revised the review.",
                    ),
                ),
            )
        )

    assert payload == {
        "document_type": InvestmentDocumentType.ETF_FACTSHEET,
        "route_confidence": 0.91,
        "risk_findings": ["Reflected fee disclosure risk."],
        "information_gaps": ["Reflected source-date gap."],
        "boundary_notes": ["Reflected non-advisory boundary."],
        "task_status_summary": [
            "extract_fees | succeeded | Fee facts extracted.",
            "analyze_fee_disclosure | failed | Fee disclosure analysis failed.",
        ],
    }


def test_assess_review_risk_uses_single_pass_review_output_without_document_text() -> None:
    executor = FakeExecutor(
        result=TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
            result={
                "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
                "risk_reason": "Missing disclosures require manual review.",
                "critical_issues": ["No benchmark methodology is provided."],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                ),
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            },
        )
    )
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    update = flow.assess_review_risk(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "Raw document text should not be forwarded."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_confidence=0.91,
            output=TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
                result={
                    "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
                    "extracted_facts": ["Management fee is 0.10%."],
                    "risk_findings": ["Fee disclosure is incomplete."],
                    "information_gaps": ["No benchmark methodology is provided."],
                    "boundary_notes": [
                        "This review does not assess live market conditions."
                    ],
                    "summary": "The review found a fee disclosure gap.",
                },
            ),
        )
    )

    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name,
            {
                "document_type": InvestmentDocumentType.ETF_FACTSHEET,
                "route_confidence": 0.91,
                "risk_findings": ["Fee disclosure is incomplete."],
                "information_gaps": ["No benchmark methodology is provided."],
                "boundary_notes": [
                    "This review does not assess live market conditions."
                ],
                "task_status_summary": [
                    "single_pass_review | succeeded | The review found a fee disclosure gap."
                ],
            },
        )
    ]
    assert update == {
        "risk_assessment": {
            "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
            "risk_reason": "Missing disclosures require manual review.",
            "critical_issues": ["No benchmark methodology is provided."],
            "approval_status": (
                InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
            ),
            "required_role": COMPLIANCE_REVIEWER_ROLE,
            "auto_proceed": False,
        },
        "approval_status": (
            InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
        ),
        "approval_required_role": COMPLIANCE_REVIEWER_ROLE,
    }


def test_build_final_result_preserves_route_metadata_for_synthesized_review() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    synthesized_review = {
        "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
        "extracted_facts": ["Management fee is 0.10%."],
        "risk_findings": ["Fee disclosure is concise but limited."],
        "information_gaps": ["No portfolio turnover disclosure found."],
        "boundary_notes": ["This review does not provide investment advice."],
        "summary": "The factsheet discloses a 0.10% management fee.",
        "learning_next_steps": [],
    }

    update = flow.build_final_result(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="The excerpt clearly matches an ETF factsheet.",
            route_confidence=0.91,
            risk_assessment={
                "overall_risk": InvestmentDocumentReviewRiskLevel.LOW.value,
                "risk_reason": "Structured findings do not block automatic release.",
                "critical_issues": [],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                ),
                "required_role": None,
                "auto_proceed": True,
            },
            approval_status=InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value,
            approval_required_role=None,
            output=TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                result=synthesized_review,
            ),
        )
    )

    assert update["output"] == TaskResult(
        ok=True,
        task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
        result={
            ACTION_FIELD: InvestmentDocumentReviewAction.COMPLETE.value,
            DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET.value,
            ROUTE_REASON_FIELD: "The excerpt clearly matches an ETF factsheet.",
            ROUTE_CONFIDENCE_FIELD: 0.91,
            REVIEW_FIELD: synthesized_review,
            RISK_ASSESSMENT_FIELD: {
                "overall_risk": InvestmentDocumentReviewRiskLevel.LOW.value,
                "risk_reason": "Structured findings do not block automatic release.",
                "critical_issues": [],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                ),
                "required_role": None,
                "auto_proceed": True,
            },
            APPROVAL_FIELD: {
                STATUS_FIELD: InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value,
                REQUIRED_ROLE_FIELD: None,
            },
        },
    )


def test_build_pending_approval_result_returns_pending_action_and_approval_fields() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    synthesized_review = {
        "document_type": InvestmentDocumentType.ETF_FACTSHEET.value,
        "extracted_facts": ["Management fee is 0.10%."],
        "risk_findings": ["Benchmark methodology disclosure is missing."],
        "information_gaps": ["No benchmark methodology is provided."],
        "boundary_notes": ["This review does not provide investment advice."],
        "summary": "The factsheet omits benchmark methodology details.",
    }

    update = flow.build_pending_approval_result(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="The excerpt clearly matches an ETF factsheet.",
            route_confidence=0.91,
            risk_assessment={
                "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
                "risk_reason": "Missing disclosures require manual review.",
                "critical_issues": ["No benchmark methodology is provided."],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                ),
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            },
            approval_status=(
                InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
            ),
            approval_required_role=COMPLIANCE_REVIEWER_ROLE,
            output=TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                result=synthesized_review,
            ),
        )
    )

    assert update["output"] == TaskResult(
        ok=True,
        task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
        result={
            ACTION_FIELD: (
                InvestmentDocumentReviewAction.PENDING_HUMAN_APPROVAL.value
            ),
            DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET.value,
            ROUTE_REASON_FIELD: "The excerpt clearly matches an ETF factsheet.",
            ROUTE_CONFIDENCE_FIELD: 0.91,
            REVIEW_FIELD: synthesized_review,
            RISK_ASSESSMENT_FIELD: {
                "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
                "risk_reason": "Missing disclosures require manual review.",
                "critical_issues": ["No benchmark methodology is provided."],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                ),
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            },
            APPROVAL_FIELD: {
                STATUS_FIELD: (
                    InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                ),
                REQUIRED_ROLE_FIELD: COMPLIANCE_REVIEWER_ROLE,
            },
        },
    )


def test_build_pending_approval_result_does_not_require_todo_resume_to_rebuild_review() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    decided_at = datetime(2026, 6, 12, 10, 30, tzinfo=timezone.utc)

    update = flow.build_pending_approval_result(
        InvestmentDocumentReviewState(
            session_id="session-pending-approval",
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            route_reason="The excerpt clearly matches an ETF factsheet.",
            route_confidence=0.91,
            risk_assessment={
                "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
                "risk_reason": "Missing disclosures require manual review.",
                "critical_issues": ["No benchmark methodology is provided."],
                "approval_status": (
                    InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
                ),
                "required_role": COMPLIANCE_REVIEWER_ROLE,
                "auto_proceed": False,
            },
            approval_status=(
                InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
            ),
            approval_required_role=COMPLIANCE_REVIEWER_ROLE,
            approval_decision_at=decided_at,
            approval_actor_role="compliance_reviewer",
            output=TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
                result={"summary": "Review already completed before approval."},
            ),
        )
    )

    assert update["output"].result is not None
    assert (
        update["output"].result[ACTION_FIELD]
        == InvestmentDocumentReviewAction.PENDING_HUMAN_APPROVAL.value
    )
    assert update["output"].result[REVIEW_FIELD] == {
        "summary": "Review already completed before approval."
    }


def test_route_after_risk_assessment_returns_pending_route_for_manual_review() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )

    route = flow.route_after_risk_assessment(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            output=TaskResult(
                ok=True,
                task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
                result={"summary": "Review completed."},
            ),
            approval_status=(
                InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL.value
            ),
        )
    )

    assert route == PENDING_APPROVAL_ROUTE


def test_build_review_todo_analyze_payload_includes_dependency_results() -> None:
    flow = InvestmentDocumentReviewFlow(
        executor=FakeExecutor(),
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    analyze_task = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                }
            ],
            "summary": "Analyze fee disclosure.",
        }
    ).tasks[0]
    dependency_results = [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={
                "extracted_facts": ["Management fee is 0.10%."],
                "source_citations": ["Fee table"],
                "information_gaps": [],
                "boundary_notes": [],
                "summary": "Fee facts extracted.",
            },
        )
    ]

    payload = flow._build_review_todo_analyze_payload(
        state=InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
        ),
        task=analyze_task,
        dependency_results=dependency_results,
    )

    assert payload == {
        "task_id": "analyze_fee_disclosure",
        "task_title": "Analyze fee disclosure",
        "task_description": "Assess fee disclosure from extracted facts.",
        "completion_criteria": ["Findings cite upstream facts."],
        DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
        REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
        DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
        ANALYZE_FOCUS_FIELD: ["fee disclosure"],
        "dependency_results": [result.model_dump() for result in dependency_results],
    }


def test_execute_review_todo_plan_returns_failed_result_for_analyze_tasks_without_upstream_dependencies() -> None:
    executor = FakeExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": [],
                    "completion_criteria": ["Findings cite upstream facts."],
                }
            ],
            "summary": "Analyze fee disclosure.",
        }
    )

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt."},
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            todo_plan=todo_plan,
        )
    )

    assert update["todo_results"] == [
        TodoTaskResult(
            id="analyze_fee_disclosure",
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "todo_task_payload_not_supported",
                "message": (
                    "Analyze To-Do tasks must depend on at least one upstream task result."
                ),
                "details": {
                    "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE.value
                },
            },
        )
    ]
    assert executor.calls == []


def test_execute_review_todo_plan_dispatches_analyze_tasks_with_dependency_results() -> None:
    class AnalyzeDispatchExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            if spec.name == INVESTMENT_DOCUMENT_EXTRACT_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "extracted_facts": ["Management fee is 0.10%."],
                        "source_citations": ["Fee table"],
                        "information_gaps": [],
                        "boundary_notes": [],
                        "summary": "Fee facts extracted.",
                    },
                )

            if spec.name == INVESTMENT_DOCUMENT_ANALYZE_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "risk_findings": ["Fee disclosure is concise but limited."],
                        "information_gaps": ["No portfolio turnover disclosure found."],
                        "boundary_notes": [
                            "This review does not provide investment advice."
                        ],
                        "summary": "The fee disclosure is present but brief.",
                    },
                )

            raise AssertionError(f"Unexpected task dispatched: {spec.name}")

    executor = AnalyzeDispatchExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract and analyze fee disclosure.",
        }
    )

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            todo_plan=todo_plan,
        )
    )

    extract_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "extracted_facts": ["Management fee is 0.10%."],
            "source_citations": ["Fee table"],
            "information_gaps": [],
            "boundary_notes": [],
            "summary": "Fee facts extracted.",
        },
    )
    analyze_result = TodoTaskResult(
        id="analyze_fee_disclosure",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "risk_findings": ["Fee disclosure is concise but limited."],
            "information_gaps": ["No portfolio turnover disclosure found."],
            "boundary_notes": ["This review does not provide investment advice."],
            "summary": "The fee disclosure is present but brief.",
        },
    )

    assert update["todo_results"] == [extract_result, analyze_result]
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_EXTRACT_TASK.name,
            {
                "task_id": "extract_fees",
                "task_title": "Extract fees",
                "task_description": "Extract fee facts from the document.",
                "completion_criteria": ["Fees are listed with source citations."],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                EXTRACT_FOCUS_FIELD: ["fees"],
            },
        ),
        (
            INVESTMENT_DOCUMENT_ANALYZE_TASK.name,
            {
                "task_id": "analyze_fee_disclosure",
                "task_title": "Analyze fee disclosure",
                "task_description": "Assess fee disclosure from extracted facts.",
                "completion_criteria": ["Findings cite upstream facts."],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                ANALYZE_FOCUS_FIELD: ["fee disclosure"],
                "dependency_results": [extract_result.model_dump()],
            },
        ),
    ]


def test_execute_review_todo_plan_runs_independent_extract_tasks_concurrently() -> None:
    class BlockingExtractExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []
            self._lock = Lock()
            self.active_calls = 0
            self.max_active_calls = 0

        def run(self, spec, payload: dict) -> TaskResult:
            with self._lock:
                self.calls.append((spec.name, payload))
                self.active_calls += 1
                self.max_active_calls = max(self.max_active_calls, self.active_calls)

            try:
                sleep(0.2)
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "extracted_facts": [f"Handled {payload['task_id']}."],
                        "source_citations": [f"Chunk for {payload['task_id']}"],
                        "information_gaps": [],
                        "boundary_notes": [],
                        "summary": f"Completed {payload['task_id']}.",
                    },
                )
            finally:
                with self._lock:
                    self.active_calls -= 1

    executor = BlockingExtractExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_chunk_0001",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract chunk 1",
                    "description": "Extract facts from chunk 1.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Chunk 1 facts are extracted."],
                },
                {
                    "id": "extract_chunk_0002",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract chunk 2",
                    "description": "Extract facts from chunk 2.",
                    "payload": {"extract_focus": ["holdings"]},
                    "depends_on": [],
                    "completion_criteria": ["Chunk 2 facts are extracted."],
                },
                {
                    "id": "extract_chunk_0003",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract chunk 3",
                    "description": "Extract facts from chunk 3.",
                    "payload": {"extract_focus": ["risks"]},
                    "depends_on": [],
                    "completion_criteria": ["Chunk 3 facts are extracted."],
                },
            ],
            "summary": "Extract three independent chunks.",
        }
    )

    started_at = perf_counter()
    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt split into several chunks.",
                REVIEW_GOAL_FIELD: "Extract facts from each chunk.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            todo_plan=todo_plan,
        )
    )
    duration = perf_counter() - started_at

    assert len(update["todo_results"]) == 3
    assert all(
        result.status == TodoTaskStatus.SUCCEEDED for result in update["todo_results"]
    )
    assert executor.max_active_calls >= 2
    assert duration < 0.45


def test_execute_review_todo_plan_runs_flow_generated_chunk_plan_concurrently() -> None:
    class FlowGeneratedChunkPlanExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []
            self._lock = Lock()
            self.active_extract_calls = 0
            self.max_active_extract_calls = 0

        def run(self, spec, payload: dict) -> TaskResult:
            with self._lock:
                self.calls.append((spec.name, payload))

            if spec.name == INVESTMENT_DOCUMENT_EXTRACT_TASK.name:
                with self._lock:
                    self.active_extract_calls += 1
                    self.max_active_extract_calls = max(
                        self.max_active_extract_calls,
                        self.active_extract_calls,
                    )

                try:
                    sleep(0.2)
                    return TaskResult(
                        ok=True,
                        task_name=spec.name,
                        result={
                            "extracted_facts": [f"Handled {payload['task_id']}."],
                            "source_citations": [f"Chunk for {payload['task_id']}"],
                            "information_gaps": [],
                            "boundary_notes": [],
                            "summary": f"Completed {payload['task_id']}.",
                        },
                    )
                finally:
                    with self._lock:
                        self.active_extract_calls -= 1

            if spec.name == INVESTMENT_DOCUMENT_ANALYZE_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "risk_findings": [f"Analyzed {payload['task_id']}."],
                        "information_gaps": [],
                        "boundary_notes": [],
                        "summary": f"Completed {payload['task_id']}.",
                    },
                )

            if spec.name == INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "risk_findings": ["Synthesized review."],
                        "information_gaps": [],
                        "boundary_notes": [],
                        "summary": "Completed synthesized review.",
                    },
                )

            raise AssertionError(f"Unexpected task dispatched: {spec.name}")

    executor = FlowGeneratedChunkPlanExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    state = InvestmentDocumentReviewState(
        input_payload={
            DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt split into several chunks.",
            REVIEW_GOAL_FIELD: "Review fees, holdings, and risks.",
        },
        document_type=InvestmentDocumentType.ETF_FACTSHEET,
        review_payload={
            DOCUMENT_TEXT_FIELD: "ETF factsheet excerpt split into several chunks.",
            DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
            EXTRACT_FOCUS_FIELD: ["fees", "holdings", "risks"],
            ANALYZE_FOCUS_FIELD: ["fees", "holdings", "risks"],
            REVIEW_GOAL_FIELD: "Review fees, holdings, and risks.",
        },
        document_chunks=["chunk 1", "chunk 2", "chunk 3"],
    )
    todo_plan = flow.generate_review_todo_plan(state)["todo_plan"]

    started_at = perf_counter()
    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload=state.input_payload,
            document_type=state.document_type,
            review_payload=state.review_payload,
            document_chunks=state.document_chunks,
            todo_plan=todo_plan,
        )
    )
    duration = perf_counter() - started_at

    assert len(update["todo_results"]) == 7
    assert executor.max_active_extract_calls >= 2
    assert duration < 0.45
    called_task_names = [call[0] for call in executor.calls]
    assert called_task_names[:3] == [
        INVESTMENT_DOCUMENT_EXTRACT_TASK.name,
        INVESTMENT_DOCUMENT_EXTRACT_TASK.name,
        INVESTMENT_DOCUMENT_EXTRACT_TASK.name,
    ]
    assert called_task_names[-1] == INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name


def test_execute_review_todo_plan_does_not_treat_prior_results_as_resume_state() -> None:
    class NoResumeExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
            if spec.name == INVESTMENT_DOCUMENT_EXTRACT_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "extracted_facts": ["Updated management fee is 0.10%."],
                        "source_citations": ["Updated fee table"],
                        "information_gaps": [],
                        "boundary_notes": [],
                        "summary": "Fresh fee facts extracted.",
                    },
                )

            if spec.name == INVESTMENT_DOCUMENT_ANALYZE_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "risk_findings": ["Updated fee disclosure is still concise."],
                        "information_gaps": [],
                        "boundary_notes": ["This review does not provide investment advice."],
                        "summary": "The refreshed fee disclosure remains brief.",
                    },
                )

            raise AssertionError(f"Unexpected task dispatched: {spec.name}")

    executor = NoResumeExecutor()
    flow = InvestmentDocumentReviewFlow(
        executor=executor,
        llm_router=FakeDocumentReviewRouter(
            InvestmentDocumentReviewRouteDecision(
                document_type=InvestmentDocumentType.ETF_FACTSHEET,
                confidence=0.91,
                reason="unused",
            )
        ),
    )
    todo_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract and analyze fee disclosure.",
        }
    )
    prior_extract_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "extracted_facts": ["Stale management fee is 0.25%."],
            "source_citations": ["Old fee table"],
            "information_gaps": ["Fee table may be outdated."],
            "boundary_notes": [],
            "summary": "Old fee facts extracted.",
        },
    )

    update = flow.execute_review_todo_plan(
        InvestmentDocumentReviewState(
            input_payload={
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
            },
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            todo_plan=todo_plan,
            todo_results=[prior_extract_result],
        )
    )

    fresh_extract_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "extracted_facts": ["Updated management fee is 0.10%."],
            "source_citations": ["Updated fee table"],
            "information_gaps": [],
            "boundary_notes": [],
            "summary": "Fresh fee facts extracted.",
        },
    )
    analyze_result = TodoTaskResult(
        id="analyze_fee_disclosure",
        status=TodoTaskStatus.SUCCEEDED,
        result={
            "risk_findings": ["Updated fee disclosure is still concise."],
            "information_gaps": [],
            "boundary_notes": ["This review does not provide investment advice."],
            "summary": "The refreshed fee disclosure remains brief.",
        },
    )

    assert update["todo_results"] == [fresh_extract_result, analyze_result]
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_EXTRACT_TASK.name,
            {
                "task_id": "extract_fees",
                "task_title": "Extract fees",
                "task_description": "Extract fee facts from the document.",
                "completion_criteria": ["Fees are listed with source citations."],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                EXTRACT_FOCUS_FIELD: ["fees"],
            },
        ),
        (
            INVESTMENT_DOCUMENT_ANALYZE_TASK.name,
            {
                "task_id": "analyze_fee_disclosure",
                "task_title": "Analyze fee disclosure",
                "task_description": "Assess fee disclosure from extracted facts.",
                "completion_criteria": ["Findings cite upstream facts."],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                REVIEW_GOAL_FIELD: "Assess whether the fee disclosure is sufficient.",
                DOCUMENT_TEXT_FIELD: "The ETF factsheet lists a 0.10% management fee.",
                ANALYZE_FOCUS_FIELD: ["fee disclosure"],
                "dependency_results": [fresh_extract_result.model_dump()],
            },
        ),
    ]


def test_document_review_flow_returns_chunk_synthesis_error_when_extract_never_succeeds() -> None:
    error_result = TaskResult(
        ok=False,
        task_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
        error=TaskError(
            error_type="input_validation_failed",
            stage="input_validation",
            user_safe_message="The input does not match the task requirements.",
        ),
    )
    executor = FakeExecutor(result=error_result)
    router = FakeDocumentReviewRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.FUND_PROSPECTUS,
            confidence=0.88,
            reason="The excerpt looks like a prospectus.",
        )
    )
    flow = InvestmentDocumentReviewFlow(executor=executor, llm_router=router)

    long_document = "\n\n".join(
        [
            (
                f"Section {idx}: This prospectus covers redemption rules, fees, "
                "liquidity constraints, investor eligibility, risk factors, and "
                "disclosure limits. "
            )
            * 3
            for idx in range(8)
        ]
    )

    result = flow.run({DOCUMENT_TEXT_FIELD: long_document})

    assert result.ok is False
    assert result.task_name == INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name
    assert result.error is not None
    assert result.error.error_type == "structured_output_failed"
    assert result.error.stage == "output_validation"
    assert result.error.debug_message == (
        "Chunk-based document review did not produce synthesis."
    )
    assert len(router.calls) == 1
    assert len(executor.calls) > 3
    assert {call[0] for call in executor.calls} == {
        INVESTMENT_DOCUMENT_EXTRACT_TASK.name
    }
