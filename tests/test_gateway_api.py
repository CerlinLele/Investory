from fastapi.testclient import TestClient

from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.main import create_app


class FakeTaskExecutor:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.task_name: str | None = None
        self.payload: dict | None = None

    def run(self, spec, payload: dict) -> TaskResult:
        self.task_name = spec.name
        self.payload = payload
        return self.result


def test_health_returns_app_config():
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "app_name": app.state.config.app_name,
        "app_env": app.state.config.app_env,
    }


def test_tasks_runs_qa_alias_through_task_executor():
    app = create_app()
    executor = FakeTaskExecutor(
        TaskResult(
            ok=True,
            task_name="finance_qa",
            result={
                "answer": "An ETF is a basket of assets.",
                "concept_explanation": "It can hold several securities.",
                "evidence": ["ETF is a basket of assets."],
                "common_misunderstandings": [],
                "risk_notice": "This is not investment advice.",
                "uncertainty": "Only the provided material was used.",
            },
        )
    )
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
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["task_name"] == "finance_qa"
    assert body["session_id"]
    assert body["result"]["answer"] == "An ETF is a basket of assets."
    assert body["error"] is None
    assert executor.task_name == "finance_qa"
    assert executor.payload == {
        "material_text": "ETF is a basket of assets.",
        "question": "What is ETF?",
    }


def test_tasks_reuses_request_session_id():
    app = create_app()
    app.state.task_executor = FakeTaskExecutor(
        TaskResult(ok=True, task_name="finance_qa", result={"answer": "ok"})
    )
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "finance_qa",
            "payload": {
                "material_text": "ETF is a basket of assets.",
                "question": "What is ETF?",
            },
            "session_id": "session-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "session-1"


def test_tasks_returns_error_response_for_executor_failure():
    app = create_app()
    app.state.task_executor = FakeTaskExecutor(
        TaskResult(
            ok=False,
            task_name="finance_qa",
            error=TaskError(
                error_type="input_validation_failed",
                stage="input_validation",
                user_safe_message="The input does not match the task requirements.",
            ),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "qa",
            "payload": {"question": "What is ETF?"},
            "session_id": "session-1",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body == {
        "ok": False,
        "task_name": "finance_qa",
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


def test_tasks_returns_400_for_unknown_task_type():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/tasks",
        json={
            "task_type": "study_plan",
            "payload": {"material_text": "ETF is a basket of assets."},
        },
    )

    body = response.json()
    assert response.status_code == 400
    assert body["ok"] is False
    assert body["task_name"] is None
    assert body["session_id"]
    assert body["result"] is None
    assert body["error"]["error_type"] == "input_validation_failed"
    assert body["error"]["stage"] == "input_validation"
    assert "Unknown task type 'study_plan'" in body["error"]["user_safe_message"]


def test_tasks_returns_422_for_missing_required_fields():
    app = create_app()
    client = TestClient(app)

    response = client.post("/tasks", json={"task_type": "qa"})

    assert response.status_code == 422
