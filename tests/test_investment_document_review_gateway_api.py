from fastapi import FastAPI
from fastapi.testclient import TestClient

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewRouteDecision,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
    ACTION_FIELD,
    INVESTMENT_DOCUMENT_REVIEW_TASK_NAME,
    InvestmentDocumentReviewFlow,
)
from investory.agent_core.runtime.flow.investment_document_review.document_review_rules import (
    DOCUMENT_ROUTER_MAX_CHARS,
)
from investory.gateway.api import (
    INVESTMENT_DOCUMENT_REVIEW_FLOW_STATE_ATTR,
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
        return TaskResult(
            ok=True,
            task_name=spec.name,
            result={"handled_by": spec.name},
        )


class FakeRouter:
    def __init__(self, decision: InvestmentDocumentReviewRouteDecision) -> None:
        self.decision = decision

    def route(self, payload: dict) -> InvestmentDocumentReviewRouteDecision:
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
        "/investment-document-review",
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
        "/investment-document-review",
        json={"payload": payload, "session_id": "session-1"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == INVESTMENT_DOCUMENT_REVIEW_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["result"][ACTION_FIELD] == "complete"
    assert len(executor.calls) == 1


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
        "/investment-document-review",
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
