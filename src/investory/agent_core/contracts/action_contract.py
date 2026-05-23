from typing import Any, Final, Literal

from pydantic import BaseModel, Field

from investory.agent_core.contracts.result_types import TaskError

ASK_MISSING_FIELDS: Final[str] = "ask_missing_fields"
RUN_TASK_MODEL: Final[str] = "run_task_model"
RUN_TOOL: Final[str] = "run_tool"
REFUSE_INVESTMENT_ADVICE: Final[str] = "refuse_investment_advice"

ActionName = Literal[
    ASK_MISSING_FIELDS,
    RUN_TASK_MODEL,
    RUN_TOOL,
    REFUSE_INVESTMENT_ADVICE,
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
