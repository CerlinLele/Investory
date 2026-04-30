import pytest
from pydantic import ValidationError

from investory.gateway.schemas import (
    HealthResponse,
    TaskErrorResponse,
    TaskRequest,
    TaskResponse,
)


def test_task_request_accepts_minimal_required_fields():
    request = TaskRequest.model_validate(
        {
            "task_type": "qa",
            "payload": {
                "material_text": "ETF is a basket of assets.",
                "question": "What is ETF?",
            },
        }
    )

    assert request.task_type == "qa"
    assert request.session_id is None
    assert request.payload["question"] == "What is ETF?"


def test_task_request_requires_task_type_and_payload():
    with pytest.raises(ValidationError) as exc_info:
        TaskRequest.model_validate({"task_type": "qa"})

    errors = exc_info.value.errors()
    assert errors[0]["type"] == "missing"
    assert errors[0]["loc"] == ("payload",)


def test_task_request_rejects_blank_task_type():
    with pytest.raises(ValidationError):
        TaskRequest.model_validate({"task_type": "  ", "payload": {}})


def test_health_response_shape():
    response = HealthResponse(ok=True, app_name="Investory", app_env="dev")

    assert response.model_dump() == {
        "ok": True,
        "app_name": "Investory",
        "app_env": "dev",
    }


def test_task_response_shape_with_error():
    response = TaskResponse(
        ok=False,
        task_name="finance_qa",
        session_id="session-1",
        error=TaskErrorResponse(
            error_type="input_validation_failed",
            stage="input_validation",
            user_safe_message="Please check the task input.",
        ),
    )

    assert response.result is None
    assert response.error is not None
    assert response.error.retryable is False
    assert response.model_dump()["error"]["error_type"] == "input_validation_failed"
