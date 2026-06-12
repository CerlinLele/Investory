from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
    ACTION_FIELD,
    APPROVAL_FIELD,
    DOCUMENT_TYPE_FIELD,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    MESSAGE_FIELD,
    MISSING_FIELDS_FIELD,
    REVIEW_FIELD,
    REQUIRED_ROLE_FIELD,
    RISK_ASSESSMENT_FIELD,
    ROUTE_CONFIDENCE_FIELD,
    ROUTE_REASON_FIELD,
    STATUS_FIELD,
    InvestmentDocumentReviewFlow,
)
from investory.agent_core.task_models.investment_document_review import (
    COMPLIANCE_REVIEWER_ROLE,
    InvestmentDocumentReviewApprovalStatus,
    InvestmentDocumentReviewRiskLevel,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    DOCUMENT_ROUTER_MAX_CHARS,
)
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
)
from investory.gateway.api import (
    INVESTMENT_DOCUMENT_REVIEW_FLOW_STATE_ATTR,
    INVESTMENT_DOCUMENT_REVIEW_FILE_ROUTE,
    INVESTMENT_DOCUMENT_REVIEW_ROUTE,
    execute_investment_document_review_request,
    router,
)
from investory.gateway.schemas import InvestmentDocumentReviewRequest


class FakeFlow:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.calls: list[tuple[dict, str | None]] = []

    def run(self, payload: dict, *, session_id: str | None = None) -> TaskResult:
        self.calls.append((payload, session_id))
        return self.result


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec.name, payload))
        if spec.name == "investment_document_risk_assessment":
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result={
                    "overall_risk": InvestmentDocumentReviewRiskLevel.LOW.value,
                    "risk_reason": "Structured findings do not block automatic release.",
                    "critical_issues": [],
                    "approval_status": (
                        InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED.value
                    ),
                    "required_role": None,
                    "auto_proceed": True,
                },
            )
        return TaskResult(
            ok=True,
            task_name=spec.name,
            result={"handled_by": spec.name},
        )


class FakeRouter:
    def __init__(self, decision: InvestmentDocumentReviewRouteDecision) -> None:
        self.decision = decision
        self.calls: list[dict] = []

    def route(self, payload: dict) -> InvestmentDocumentReviewRouteDecision:
        self.calls.append(payload)
        return self.decision


def _client_with_flow(flow) -> TestClient:
    app = FastAPI()
    setattr(app.state, INVESTMENT_DOCUMENT_REVIEW_FLOW_STATE_ATTR, flow)
    app.include_router(router)
    return TestClient(app)


def test_execute_investment_document_review_request_runs_injected_flow():
    flow = FakeFlow(
        TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={"action": "ask_for_missing_input"},
        )
    )
    request = InvestmentDocumentReviewRequest(
        payload={"document_text": "ETF factsheet"},
        session_id="session-1",
    )

    response = execute_investment_document_review_request(request, flow=flow)

    assert response.ok is True
    assert response.task_name == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert response.session_id == "session-1"
    assert response.result == {"action": "ask_for_missing_input"}
    assert flow.calls == [({"document_text": "ETF factsheet"}, "session-1")]


def test_investment_document_review_endpoint_returns_missing_input_branch():
    executor = FakeExecutor()
    client = _client_with_flow(InvestmentDocumentReviewFlow(executor=executor))

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={
            "payload": {"review_goal": "Check fees"},
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["result"][ACTION_FIELD] == "ask_for_missing_input"
    assert executor.calls == []


def test_investment_document_review_endpoint_runs_complete_review_through_executor():
    executor = FakeExecutor()
    payload = {
        "document_text": "A" * (DOCUMENT_ROUTER_MAX_CHARS + 50),
        "document_type_hint": "etf_factsheet",
    }
    router = FakeRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    client = _client_with_flow(
        InvestmentDocumentReviewFlow(executor=executor, llm_router=router)
    )

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={"payload": payload, "session_id": "session-1"},
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"ok", "task_name", "session_id", "result", "error"}
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["error"] is None
    assert body["result"] == {
        ACTION_FIELD: "complete",
        DOCUMENT_TYPE_FIELD: "etf_factsheet",
        ROUTE_REASON_FIELD: "The excerpt clearly matches an ETF factsheet.",
        ROUTE_CONFIDENCE_FIELD: 0.91,
        REVIEW_FIELD: {"handled_by": "investment_document_synthesize"},
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
    }
    call_names = [name for name, _ in executor.calls]
    assert call_names.count("investment_document_extract") == 2
    assert call_names.count("investment_document_analyze") >= 1
    assert call_names[-2:] == [
        "investment_document_synthesize",
        "investment_document_risk_assessment",
    ]


def test_investment_document_review_endpoint_returns_pending_approval_for_high_risk_review():
    class HighRiskExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def run(self, spec, payload: dict) -> TaskResult:
            self.calls.append((spec.name, payload))
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
            if spec.name == INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name:
                return TaskResult(
                    ok=True,
                    task_name=spec.name,
                    result={
                        "document_type": "etf_factsheet",
                        "extracted_facts": ["Management fee is 0.03%."],
                        "risk_findings": ["Benchmark methodology is not disclosed."],
                        "information_gaps": ["No benchmark methodology is provided."],
                        "boundary_notes": [
                            "The review does not assess live market conditions."
                        ],
                        "summary": "The factsheet omits benchmark methodology details.",
                    },
                )
            return TaskResult(
                ok=True,
                task_name=spec.name,
                result={"handled_by": spec.name},
            )

    payload = {
        "document_text": "The ETF factsheet lists fees but omits benchmark details.",
        "document_type_hint": "etf_factsheet",
    }
    router = FakeRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="The excerpt clearly matches an ETF factsheet.",
        )
    )
    client = _client_with_flow(
        InvestmentDocumentReviewFlow(executor=HighRiskExecutor(), llm_router=router)
    )

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={"payload": payload, "session_id": "session-high-risk"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-high-risk"
    assert body["error"] is None
    assert body["result"] == {
        ACTION_FIELD: "pending_human_approval",
        DOCUMENT_TYPE_FIELD: "etf_factsheet",
        ROUTE_REASON_FIELD: "The excerpt clearly matches an ETF factsheet.",
        ROUTE_CONFIDENCE_FIELD: 0.91,
        REVIEW_FIELD: {
            "document_type": "etf_factsheet",
            "extracted_facts": ["Management fee is 0.03%."],
            "risk_findings": ["Benchmark methodology is not disclosed."],
            "information_gaps": ["No benchmark methodology is provided."],
            "boundary_notes": [
                "The review does not assess live market conditions."
            ],
            "summary": "The factsheet omits benchmark methodology details.",
        },
        RISK_ASSESSMENT_FIELD: {
            "overall_risk": InvestmentDocumentReviewRiskLevel.HIGH.value,
            "risk_reason": "A material disclosure gap requires manual approval.",
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
    }


def test_investment_document_review_endpoint_preserves_refusal_branch():
    executor = FakeExecutor()
    router = FakeRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.ETF_FACTSHEET,
            confidence=0.91,
            reason="unused because policy gate refuses first.",
        )
    )
    client = _client_with_flow(
        InvestmentDocumentReviewFlow(executor=executor, llm_router=router)
    )

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={
            "payload": {
                "document_text": "ETF factsheet with fee table.",
                "review_goal": "Should I buy this ETF today?",
            },
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"ok", "task_name", "session_id", "result", "error"}
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["error"] is None
    assert body["result"][ACTION_FIELD] == "refuse_and_redirect"
    assert MESSAGE_FIELD in body["result"]
    assert router.calls == []
    assert executor.calls == []


def test_investment_document_review_endpoint_preserves_unknown_type_branch():
    executor = FakeExecutor()
    router = FakeRouter(
        InvestmentDocumentReviewRouteDecision(
            document_type=InvestmentDocumentType.UNKNOWN,
            confidence=0.33,
            reason="The excerpt does not clearly identify a supported document type.",
        )
    )
    client = _client_with_flow(
        InvestmentDocumentReviewFlow(executor=executor, llm_router=router)
    )

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={
            "payload": {
                "document_text": "A short unlabeled investment note.",
            },
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"ok", "task_name", "session_id", "result", "error"}
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["error"] is None
    assert body["result"][ACTION_FIELD] == "ask_for_missing_input"
    assert body["result"][MISSING_FIELDS_FIELD] == ["document_type_hint"]
    assert MESSAGE_FIELD in body["result"]
    assert len(router.calls) == 1
    assert executor.calls == []


def test_investment_document_review_endpoint_returns_error_response_for_flow_failure():
    flow = FakeFlow(
        TaskResult(
            ok=False,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            error=TaskError(
                error_type="input_validation_failed",
                stage="input_validation",
                user_safe_message="The input does not match the task requirements.",
            ),
        )
    )
    client = _client_with_flow(flow)

    response = client.post(
        INVESTMENT_DOCUMENT_REVIEW_ROUTE,
        json={
            "payload": {"document_text": "ETF factsheet"},
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body == {
        "ok": False,
        "task_name": INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
        "session_id": "session-1",
        "result": None,
        "error": {
            "error_type": "input_validation_failed",
            "stage": "input_validation",
            "user_safe_message": "The input does not match the task requirements.",
            "retryable": False,
            "request_id": None,
        },
    }


def test_investment_document_review_file_endpoint_runs_flow_without_event_loop_error():
    flow = FakeFlow(
        TaskResult(
            ok=True,
            task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
            result={"action": "complete", "document_type": "learning_material"},
        )
    )
    client = _client_with_flow(flow)

    with patch(
        "investory.gateway.api.extract_text_from_pdf",
        return_value="Extracted PDF text for review.",
    ):
        response = client.post(
            INVESTMENT_DOCUMENT_REVIEW_FILE_ROUTE,
            files={
                "file": (
                    "sample.pdf",
                    b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
                    "application/pdf",
                )
            },
            data={
                "review_goal": "Summarize the document",
                "document_type_hint": "learning_material",
                "session_id": "session-file-1",
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-file-1"
    assert body["result"] == {"action": "complete", "document_type": "learning_material"}
    assert flow.calls == [
        (
            {
                "document_text": "Extracted PDF text for review.",
                "review_goal": "Summarize the document",
                "document_type_hint": "learning_material",
            },
            "session-file-1",
        )
    ]
