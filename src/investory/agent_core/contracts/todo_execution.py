from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Todo task kind identifiers
FINANCE_QA_TASK_KIND = "finance_qa"
LEARNING_MATERIAL_SUMMARY_TASK_KIND = "learning_material_summary"
INSTRUMENT_BRIEF_TASK_KIND = "instrument_brief"
SYNTHESIZE_RESULTS_TASK_KIND = "synthesize_results"
INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND = "investment_document_extract"
INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND = "investment_document_analyze"
INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND = "investment_document_synthesize"

# Todo task status identifiers
PENDING_TASK_STATUS = "pending"
RUNNING_TASK_STATUS = "running"
SUCCEEDED_TASK_STATUS = "succeeded"
FAILED_TASK_STATUS = "failed"
SKIPPED_TASK_STATUS = "skipped"

# Todo execution failure policy identifiers
FAIL_FAST_FAILURE_POLICY = "fail_fast"
BEST_EFFORT_FAILURE_POLICY = "best_effort"
RETRY_THEN_FAIL_FAILURE_POLICY = "retry_then_fail"


class TodoTaskKind(str, Enum):
    FINANCE_QA = FINANCE_QA_TASK_KIND
    LEARNING_MATERIAL_SUMMARY = LEARNING_MATERIAL_SUMMARY_TASK_KIND
    INSTRUMENT_BRIEF = INSTRUMENT_BRIEF_TASK_KIND
    SYNTHESIZE_RESULTS = SYNTHESIZE_RESULTS_TASK_KIND
    INVESTMENT_DOCUMENT_EXTRACT = INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND
    INVESTMENT_DOCUMENT_ANALYZE = INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND
    INVESTMENT_DOCUMENT_SYNTHESIZE = INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND


class TodoTaskStatus(str, Enum):
    PENDING = PENDING_TASK_STATUS
    RUNNING = RUNNING_TASK_STATUS
    SUCCEEDED = SUCCEEDED_TASK_STATUS
    FAILED = FAILED_TASK_STATUS
    SKIPPED = SKIPPED_TASK_STATUS


class TodoFailurePolicy(str, Enum):
    FAIL_FAST = FAIL_FAST_FAILURE_POLICY
    BEST_EFFORT = BEST_EFFORT_FAILURE_POLICY
    RETRY_THEN_FAIL = RETRY_THEN_FAIL_FAILURE_POLICY


class TodoTaskSpec(BaseModel):
    id: str
    kind: TodoTaskKind
    title: str
    description: str
    payload: dict[str, Any]
    depends_on: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)


class TodoExecutionPlan(BaseModel):
    tasks: list[TodoTaskSpec]
    summary: str
    failure_policy: TodoFailurePolicy = TodoFailurePolicy.RETRY_THEN_FAIL


class TodoTaskResult(BaseModel):
    id: str
    status: TodoTaskStatus
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class TodoExecutionResumeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    session_id: str | None = None
    plan: TodoExecutionPlan
    results_by_id: dict[str, TodoTaskResult] = Field(default_factory=dict)
    attempts_by_id: dict[str, int] = Field(default_factory=dict)
    updated_at: datetime

    @model_validator(mode="after")
    def validate_resume_maps(self):
        plan_task_ids = {task.id for task in self.plan.tasks}

        unknown_result_ids = sorted(set(self.results_by_id) - plan_task_ids)
        if unknown_result_ids:
            raise ValueError(
                "Resume results_by_id contains unknown task ids: "
                + ", ".join(unknown_result_ids)
            )

        mismatched_result_ids = sorted(
            task_id
            for task_id, result in self.results_by_id.items()
            if result.id != task_id
        )
        if mismatched_result_ids:
            raise ValueError(
                "Resume results_by_id keys must match TodoTaskResult.id: "
                + ", ".join(mismatched_result_ids)
            )

        unknown_attempt_ids = sorted(set(self.attempts_by_id) - plan_task_ids)
        if unknown_attempt_ids:
            raise ValueError(
                "Resume attempts_by_id contains unknown task ids: "
                + ", ".join(unknown_attempt_ids)
            )

        negative_attempt_ids = sorted(
            task_id
            for task_id, attempts in self.attempts_by_id.items()
            if attempts < 0
        )
        if negative_attempt_ids:
            raise ValueError(
                "Resume attempts_by_id values must be zero or greater: "
                + ", ".join(negative_attempt_ids)
            )

        return self
