from typing import Any, Literal

from pydantic import BaseModel, Field

from investory.agent_core.contracts.result_types import TaskError


ActionName = Literal[
    "ask_missing_fields",
    "run_task_model",
    "refuse_investment_advice",
    "fetch_then_run_instrument_brief",
    "run_web_search",
]

ActionStatus = Literal["success", "failed", "requires_user_input", "refused"]


class TaskDecision(BaseModel):
    action: ActionName
    task_name: str
    reason: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    params: dict[str, Any] = Field(default_factory=dict)
    user_message: str | None = None
    need_user_confirmation: bool = False


class ActionCall(BaseModel):
    action: ActionName
    task_name: str
    params: dict[str, Any]
    decision_reason: str
    request_id: str | None = None


class ActionResult(BaseModel):
    action: ActionName
    task_name: str
    status: ActionStatus
    result: dict[str, Any] | None = None
    error: TaskError | None = None
    user_message: str | None = None
