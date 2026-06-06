import asyncio

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoFailurePolicy,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.todo_core.runner import TodoExecutionRunner


def test_todo_execution_runner_retries_failed_task_until_success() -> None:
    attempts_by_id: dict[str, int] = {}

    async def executor(task) -> TodoTaskResult:
        attempts_by_id[task.id] = attempts_by_id.get(task.id, 0) + 1
        if attempts_by_id[task.id] < 3:
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.FAILED,
                error={
                    "error_type": "transient_failure",
                    "message": "Temporary extraction failure.",
                },
            )

        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted after retry."},
        )

    plan = TodoExecutionPlan.model_validate(
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

    results = asyncio.run(TodoExecutionRunner(executor, max_retries=2).run(plan))

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted after retry."},
        )
    ]
    assert attempts_by_id == {"extract_fees": 3}


def test_todo_execution_runner_skips_downstream_task_after_retry_exhaustion() -> None:
    attempts_by_id: dict[str, int] = {}

    async def executor(task) -> TodoTaskResult:
        attempts_by_id[task.id] = attempts_by_id.get(task.id, 0) + 1
        if task.id == "extract_fees":
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.FAILED,
                error={
                    "error_type": "persistent_failure",
                    "message": "Fee extraction kept failing.",
                },
            )

        raise AssertionError(f"Unexpected task execution: {task.id}")

    plan = TodoExecutionPlan.model_validate(
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
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract and analyze fee disclosure.",
            "failure_policy": TodoFailurePolicy.RETRY_THEN_FAIL,
        }
    )

    results = asyncio.run(TodoExecutionRunner(executor, max_retries=2).run(plan))

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "persistent_failure",
                "message": "Fee extraction kept failing.",
            },
        ),
        TodoTaskResult(
            id="analyze_fee_disclosure",
            status=TodoTaskStatus.SKIPPED,
            error={
                "error_type": "dependency_failed",
                "message": "Task skipped because one or more dependencies did not succeed.",
                "details": {"failed_dependency_task_id": "extract_fees"},
            },
        ),
    ]
    assert attempts_by_id == {"extract_fees": 3}
