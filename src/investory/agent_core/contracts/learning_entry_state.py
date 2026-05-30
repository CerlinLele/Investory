from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from investory.agent_core.contracts.result_types import TaskError, TaskResult


class LearningEntryCandidateTaskType(str, Enum):
    QA = "qa"
    SUMMARY = "summary"
    BRIEF = "brief"


class LearningEntryDecision(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    EXECUTE_LEARNING_TASK = "execute_learning_task"


class LearningEntryState(BaseModel):
    session_id: str
    input_payload: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list)
    candidate_task_type: LearningEntryCandidateTaskType | None = None
    decision: LearningEntryDecision | None = None
    resolved_task_name: str | None = None
    task_payload: dict[str, Any] | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
