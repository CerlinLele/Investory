from fastapi import FastAPI
from fastapi.testclient import TestClient

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.runtime.flow.learning_entry.learning_entry_flow import (
    ACTION_FIELD,
    LEARNING_ENTRY_TASK_NAME,
    MISSING_FIELDS_FIELD,
    LearningEntryFlow,
)
from investory.agent_core.runtime.flow.learning_entry.learning_entry_rules import (
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    UNKNOWN_INPUT_MISSING_FIELDS,
)
from investory.agent_core.tasks import FINANCE_QA_TASK
from investory.gateway.api import (
    LEARNING_ENTRY_FLOW_STATE_ATTR,
    execute_learning_entry_request,
    router,
)
from investory.gateway.schemas import LearningEntryRequest


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


def _client_with_flow(flow) -> TestClient:
    app = FastAPI()
    setattr(app.state, LEARNING_ENTRY_FLOW_STATE_ATTR, flow)
    app.include_router(router)
    return TestClient(app)


def test_execute_learning_entry_request_runs_injected_flow():
    flow = FakeFlow(
        TaskResult(
            ok=True,
            task_name=LEARNING_ENTRY_TASK_NAME,
            result={"action": "ask_for_missing_input"},
        )
    )
    request = LearningEntryRequest(
        payload={QUESTION_FIELD: "What is an ETF?"},
        session_id="session-1",
    )

    response = execute_learning_entry_request(request, flow=flow)

    assert response.ok is True
    assert response.task_name == LEARNING_ENTRY_TASK_NAME
    assert response.session_id == "session-1"
    assert response.result == {"action": "ask_for_missing_input"}
    assert flow.calls == [({QUESTION_FIELD: "What is an ETF?"}, "session-1")]


def test_learning_entry_endpoint_returns_missing_input_branch():
    executor = FakeExecutor()
    client = _client_with_flow(LearningEntryFlow(executor=executor))

    response = client.post(
        "/learning-entry",
        json={
            "payload": {QUESTION_FIELD: "What is an ETF?"},
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == LEARNING_ENTRY_TASK_NAME
    assert body["session_id"] == "session-1"
    assert body["result"][ACTION_FIELD] == "ask_for_missing_input"
    assert body["result"][MISSING_FIELDS_FIELD] == [MATERIAL_TEXT_FIELD]
    assert executor.calls == []


def test_learning_entry_endpoint_runs_complete_qa_through_executor():
    executor = FakeExecutor()
    payload = {
        MATERIAL_TEXT_FIELD: "An ETF is a basket of assets.",
        QUESTION_FIELD: "What is an ETF?",
    }
    client = _client_with_flow(LearningEntryFlow(executor=executor))

    response = client.post(
        "/learning-entry",
        json={"payload": payload, "session_id": "session-1"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == FINANCE_QA_TASK.name
    assert body["session_id"] == "session-1"
    assert body["result"] == {"handled_by": FINANCE_QA_TASK.name}
    assert executor.calls == [(FINANCE_QA_TASK.name, payload)]


def test_learning_entry_endpoint_returns_unknown_input_fallback_for_unresolved_payload():
    executor = FakeExecutor()
    client = _client_with_flow(LearningEntryFlow(executor=executor))

    response = client.post(
        "/learning-entry",
        json={"payload": {"user_input": "Help me with this ETF content."}},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == LEARNING_ENTRY_TASK_NAME
    assert body["result"][ACTION_FIELD] == "ask_for_missing_input"
    assert body["result"][MISSING_FIELDS_FIELD] == UNKNOWN_INPUT_MISSING_FIELDS
    assert executor.calls == []
