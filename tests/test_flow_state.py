import pytest
from pydantic import ValidationError

from investory.agent_core.contracts import TaskFlowState


@pytest.mark.parametrize("status", ["pending", "running", "done", "error"])
def test_task_flow_state_accepts_supported_statuses(status: str):
    state = TaskFlowState(
        task_id="task_123",
        task_name="finance_qa",
        input_payload={"question": "What is EPS?"},
        status=status,
    )

    assert state.status == status


def test_task_flow_state_defaults_to_pending():
    state = TaskFlowState(
        task_id="task_123",
        task_name="finance_qa",
        input_payload={"question": "What is EPS?"},
    )

    assert state.status == "pending"
    assert state.validated_input is None
    assert state.messages is None
    assert state.model_result is None
    assert state.output is None
    assert state.error is None
    assert state.step_count == 0
    assert state.max_steps is None
    assert state.retry_count == 0
    assert state.requires_user_input is False
    assert state.last_error is None


def test_task_flow_state_rejects_unknown_status():
    with pytest.raises(ValidationError):
        TaskFlowState(
            task_id="task_123",
            task_name="finance_qa",
            input_payload={"question": "What is EPS?"},
            status="unknown",
        )


def test_task_flow_state_requires_identity_and_payload():
    with pytest.raises(ValidationError) as exc_info:
        TaskFlowState()

    errors = exc_info.value.errors()
    missing_fields = {error["loc"][0] for error in errors}

    assert missing_fields == {"task_id", "task_name", "input_payload"}
