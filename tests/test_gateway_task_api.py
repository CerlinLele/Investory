from fastapi.testclient import TestClient

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.tasks import FINANCE_QA_TASK, INSTRUMENT_BRIEF_TASK
from investory.gateway.api import execute_task_request
from investory.gateway.schemas import TaskRequest
from investory.main import create_app


class FakeExecutor:
    def __init__(self, result: TaskResult | None = None) -> None:
        self.result = result or TaskResult(
            ok=True,
            task_name="finance_qa",
            result={"answer": "ETF means exchange-traded fund."},
        )
        self.calls: list[tuple[object, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec, payload))
        return self.result


def test_execute_task_request_returns_missing_fields_action_before_executor():
    executor = FakeExecutor()
    request = TaskRequest(
        task_type="brief",
        payload={"instrument_name_or_code": "VOO"},
        session_id="session-1",
    )

    response = execute_task_request(request, executor=executor)

    assert response.ok is True
    assert response.task_name == "instrument_brief"
    assert response.session_id == "session-1"
    assert response.error is None
    assert response.result is not None
    assert response.result["action"] == "ask_missing_fields"
    assert response.result["missing_fields"] == ["source_material"]
    assert executor.calls == []


def test_execute_task_request_runs_executor_when_payload_is_complete():
    executor = FakeExecutor()
    request = TaskRequest(
        task_type="qa",
        payload={
            "material_text": "ETF is a basket of assets.",
            "question": "What is ETF?",
        },
        session_id="session-1",
    )

    response = execute_task_request(request, executor=executor)

    assert response.ok is True
    assert response.task_name == "finance_qa"
    assert response.result == {"answer": "ETF means exchange-traded fund."}
    assert executor.calls == [
        (
            FINANCE_QA_TASK,
            {
                "material_text": "ETF is a basket of assets.",
                "question": "What is ETF?",
            },
        )
    ]


def test_tasks_endpoint_returns_missing_fields_action():
    app = create_app()
    app.state.task_executor = FakeExecutor()
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "brief",
            "payload": {},
            "session_id": "session-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["task_name"] == INSTRUMENT_BRIEF_TASK.name
    assert body["session_id"] == "session-1"
    assert body["result"]["action"] == "ask_missing_fields"
    assert body["result"]["missing_fields"] == [
        "instrument_name_or_code",
        "source_material",
    ]
    assert body["error"] is None


def test_tasks_endpoint_runs_executor_when_payload_is_complete():
    app = create_app()
    executor = FakeExecutor()
    app.state.task_executor = executor
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "qa",
            "payload": {
                "material_text": "ETF is a basket of assets.",
                "question": "What is ETF?",
            },
            "session_id": "session-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["task_name"] == "finance_qa"
    assert body["result"] == {"answer": "ETF means exchange-traded fund."}
    assert len(executor.calls) == 1


def test_tasks_endpoint_rejects_unknown_task_type():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "unknown",
            "payload": {},
        },
    )

    assert response.status_code == 400
    assert "Unknown task type 'unknown'" in response.json()["detail"]
