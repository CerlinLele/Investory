from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoFailurePolicy,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)


def _sample_plan() -> TodoExecutionPlan:
    return TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                }
            ],
            "summary": "Extract fee facts.",
            "failure_policy": TodoFailurePolicy.RETRY_THEN_FAIL,
        }
    )


def test_todo_execution_resume_state_persists_only_recovery_boundary() -> None:
    plan = _sample_plan()
    updated_at = datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc)
    result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={"summary": "Fee facts extracted."},
    )

    resume_state = TodoExecutionResumeState.model_validate(
        {
            "run_id": "review-run-1",
            "session_id": "session-1",
            "plan": plan.model_dump(),
            "results_by_id": {"extract_fees": result.model_dump()},
            "attempts_by_id": {"extract_fees": 2},
            "updated_at": updated_at,
        }
    )

    assert resume_state.model_dump() == {
        "run_id": "review-run-1",
        "session_id": "session-1",
        "plan": plan.model_dump(),
        "results_by_id": {"extract_fees": result.model_dump()},
        "attempts_by_id": {"extract_fees": 2},
        "updated_at": updated_at,
    }


def test_todo_execution_resume_state_rejects_runtime_objects() -> None:
    with pytest.raises(ValidationError) as exc_info:
        TodoExecutionResumeState.model_validate(
            {
                "run_id": "review-run-1",
                "plan": _sample_plan().model_dump(),
                "results_by_id": {},
                "attempts_by_id": {},
                "updated_at": datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
                "executor": "runtime object should not be persisted",
            }
        )

    assert "executor" in str(exc_info.value)
