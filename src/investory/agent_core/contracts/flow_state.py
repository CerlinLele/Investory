from typing import Any, Literal

from pydantic import BaseModel

from investory.agent_core.contracts.result_types import TaskError, TaskResult


TaskFlowStatus = Literal["pending", "running", "done", "error"]


class TaskFlowState(BaseModel):
    task_id: str
    task_name: str
    input_payload: dict[str, Any]
    status: TaskFlowStatus = "pending"
    validated_input: dict[str, Any] | None = None
    messages: list[Any] | None = None
    model_result: dict[str, Any] | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
    step_count: int = 0
    max_steps: int | None = None
    retry_count: int = 0
    requires_user_input: bool = False
    last_error: str | None = None
