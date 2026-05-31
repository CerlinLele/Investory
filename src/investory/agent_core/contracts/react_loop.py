from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReactLoopStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    FINALIZED = "finalized"
    FAILED = "failed"
    STOPPED = "stopped"


class ReactActionType(str, Enum):
    PLAN = "plan"
    VALIDATE = "validate"
    EXECUTE = "execute"
    CALL_TOOL = "call_tool"
    WAIT_FOR_USER = "wait_for_user"
    FINALIZE = "finalize"
    RETRY = "retry"
    FAIL = "fail"


class ReactBudget(BaseModel):
    max_steps: int = 12
    max_tool_calls: int = 8
    max_retries: int = 2


class ReactStepRecord(BaseModel):
    step_index: int
    action_type: ReactActionType
    summary: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReactToolCallRecord(BaseModel):
    step_index: int
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    success: bool | None = None
    error_code: str | None = None
    error_message: str | None = None


class ReactAuditEvent(BaseModel):
    event_type: str
    step_index: int
    status: ReactLoopStatus
    action_type: ReactActionType | None = None
    message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


class ReactLoopState(BaseModel):
    status: ReactLoopStatus = ReactLoopStatus.PENDING
    budget: ReactBudget = Field(default_factory=ReactBudget)
    step_count: int = 0
    retry_count: int = 0
    tool_call_count: int = 0
    requires_user_input: bool = False
    last_error: str | None = None
    current_action: ReactActionType | None = None
    repeated_action_count: int = 0
    step_records: list[ReactStepRecord] = Field(default_factory=list)
    tool_call_records: list[ReactToolCallRecord] = Field(default_factory=list)
    audit_events: list[ReactAuditEvent] = Field(default_factory=list)
