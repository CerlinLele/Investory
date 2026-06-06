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
    TodoTaskKind,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
    ACTION_FIELD,
    DOCUMENT_TYPE_FIELD,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    REVIEW_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    InvestmentDocumentReviewAction,
    InvestmentDocumentReviewFlow,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    get_review_framework,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
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


class FakeDocumentReviewRouter:
    def __init__(self, decision: InvestmentDocumentReviewRouteDecision) -> None:
        self.decision = decision
        self.calls: list[dict] = []

    def route(self, payload: dict) -> InvestmentDocumentReviewRouteDecision:
        self.calls.append(payload)
        return self.decision


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


def test_document_review_flow_preserves_downstream_executor_error_result() -> None:
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

    result = flow.run(
        {
            DOCUMENT_TEXT_FIELD: "This prospectus covers redemption rules and fees.",
        }
    )

    assert result is error_result
    assert len(router.calls) == 1
    assert len(executor.calls) == 1
