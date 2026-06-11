from datetime import datetime, timezone
import logging
from threading import Lock
from time import perf_counter, sleep

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
    ACTION_FIELD,
    CHUNK_REVIEW_SCOPE,
    DOCUMENT_TYPE_FIELD,
    FULL_DOCUMENT_REVIEW_SCOPE,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    REVIEW_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    InvestmentDocumentReviewAction,
    InvestmentDocumentReviewFlow,
    should_use_chunk_review,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    get_review_framework,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)


class FakeExecutor:
    def __init__(self, result: TaskResult | None = None) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec.name, payload))
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
    assert result.result[REVIEW_FIELD] == {
        "handled_by": INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name
    }
    assert executor.calls == [
        (
            INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name,
            {
                DOCUMENT_TEXT_FIELD: payload[DOCUMENT_TEXT_FIELD],
                DOCUMENT_TYPE_FIELD: InvestmentDocumentType.ETF_FACTSHEET,
                EXTRACT_FOCUS_FIELD: framework.extract_focus if framework else [],
                ANALYZE_FOCUS_FIELD: framework.analyze_focus if framework else [],
                REVIEW_GOAL_FIELD: payload[REVIEW_GOAL_FIELD],
            },
        )
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
    assert result.result[REVIEW_FIELD] == {
        "handled_by": INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name
    }
    called_task_names = [call[0] for call in executor.calls]
    assert called_task_names.count(INVESTMENT_DOCUMENT_EXTRACT_TASK.name) > 1
    assert called_task_names[-2:] == [
        INVESTMENT_DOCUMENT_ANALYZE_TASK.name,
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name,
    ]


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
        },
    )


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
