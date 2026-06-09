import asyncio
from datetime import datetime, timezone

from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoExecutionResumeState,
    TodoFailurePolicy,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.todo_core.runner import (
    TODO_EVENT_LAYER_STARTED,
    TODO_EVENT_TASK_FAILED,
    TODO_EVENT_TASK_RETRYING,
    TODO_EVENT_TASK_SKIPPED,
    TODO_EVENT_TASK_STARTED,
    TODO_EVENT_TASK_SUCCEEDED,
    TodoExecutionRunner,
)


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


def test_todo_execution_runner_accepts_matching_resume_state_parameter() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted."},
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
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor).run(plan, resume_state=resume_state)
    )

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted."},
        )
    ]
    assert calls == ["extract_fees"]


def test_todo_execution_runner_skips_succeeded_resume_tasks() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
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
                }
            ],
            "summary": "Extract fee facts.",
            "failure_policy": TodoFailurePolicy.RETRY_THEN_FAIL,
        }
    )
    resume_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={"summary": "Fee facts extracted in a previous run."},
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={"extract_fees": resume_result},
        attempts_by_id={"extract_fees": 1},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor).run(plan, resume_state=resume_state)
    )

    assert results == [resume_result]
    assert calls == []


def test_todo_execution_runner_continues_after_succeeded_resume_dependency() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
        if task.id == "analyze_fee_disclosure":
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.SUCCEEDED,
                result={"summary": "Fee disclosure analyzed from resumed facts."},
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
    resumed_extract_result = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.SUCCEEDED,
        result={"summary": "Fee facts extracted in a previous run."},
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={"extract_fees": resumed_extract_result},
        attempts_by_id={"extract_fees": 1},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor).run(plan, resume_state=resume_state)
    )

    assert results == [
        resumed_extract_result,
        TodoTaskResult(
            id="analyze_fee_disclosure",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee disclosure analyzed from resumed facts."},
        ),
    ]
    assert calls == ["analyze_fee_disclosure"]


def test_todo_execution_runner_keeps_plan_order_for_partial_success_resume() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
        if task.id == "extract_fees":
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.SUCCEEDED,
                result={"summary": "Fresh fee facts extracted."},
            )
        if task.id == "analyze_fee_disclosure":
            return TodoTaskResult(
                id=task.id,
                status=TodoTaskStatus.SUCCEEDED,
                result={"summary": "Fresh fee disclosure analysis completed."},
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
                {
                    "id": "extract_holdings",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract holdings",
                    "description": "Extract holdings facts from the document.",
                    "payload": {"extract_focus": ["holdings"]},
                    "depends_on": [],
                    "completion_criteria": ["Holdings are listed with source citations."],
                },
            ],
            "summary": "Resume a partially completed review plan.",
            "failure_policy": TodoFailurePolicy.RETRY_THEN_FAIL,
        }
    )
    resumed_holdings_result = TodoTaskResult(
        id="extract_holdings",
        status=TodoTaskStatus.SUCCEEDED,
        result={"summary": "Holdings facts extracted in a previous run."},
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={"extract_holdings": resumed_holdings_result},
        attempts_by_id={"extract_holdings": 1},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor).run(plan, resume_state=resume_state)
    )

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fresh fee facts extracted."},
        ),
        TodoTaskResult(
            id="analyze_fee_disclosure",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fresh fee disclosure analysis completed."},
        ),
        resumed_holdings_result,
    ]
    assert calls == ["extract_fees", "analyze_fee_disclosure"]


def test_todo_execution_runner_retries_only_remaining_resume_attempts() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "persistent_failure",
                "message": "Fee extraction kept failing.",
            },
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
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={
            "extract_fees": TodoTaskResult(
                id="extract_fees",
                status=TodoTaskStatus.FAILED,
                error={
                    "error_type": "transient_failure",
                    "message": "Previous attempts failed.",
                },
            )
        },
        attempts_by_id={"extract_fees": 2},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor, max_retries=2).run(
            plan,
            resume_state=resume_state,
        )
    )

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.FAILED,
            error={
                "error_type": "persistent_failure",
                "message": "Fee extraction kept failing.",
            },
        )
    ]
    assert calls == ["extract_fees"]


def test_todo_execution_runner_treats_running_resume_task_as_retry_candidate() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee extraction completed after resume."},
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
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={
            "extract_fees": TodoTaskResult(
                id="extract_fees",
                status=TodoTaskStatus.RUNNING,
                result={"summary": "Previous run stopped mid-task."},
            )
        },
        attempts_by_id={"extract_fees": 1},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor, max_retries=2).run(
            plan,
            resume_state=resume_state,
        )
    )

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee extraction completed after resume."},
        )
    ]
    assert calls == ["extract_fees"]


def test_todo_execution_runner_skips_dependency_after_exhausted_resume_failure() -> None:
    calls: list[str] = []

    async def executor(task) -> TodoTaskResult:
        calls.append(task.id)
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
    exhausted_failure = TodoTaskResult(
        id="extract_fees",
        status=TodoTaskStatus.FAILED,
        error={
            "error_type": "persistent_failure",
            "message": "Fee extraction kept failing.",
        },
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=plan,
        results_by_id={"extract_fees": exhausted_failure},
        attempts_by_id={"extract_fees": 3},
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    results = asyncio.run(
        TodoExecutionRunner(executor, max_retries=2).run(
            plan,
            resume_state=resume_state,
        )
    )

    assert results == [
        exhausted_failure,
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
    assert calls == []


def test_todo_execution_runner_rejects_resume_state_for_different_plan() -> None:
    async def executor(task) -> TodoTaskResult:
        return TodoTaskResult(
            id=task.id,
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted."},
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
        }
    )
    other_plan = TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_holdings",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract holdings",
                    "description": "Extract holdings facts from the document.",
                    "payload": {"extract_focus": ["holdings"]},
                    "depends_on": [],
                    "completion_criteria": ["Holdings are listed with source citations."],
                }
            ],
            "summary": "Extract holdings facts.",
        }
    )
    resume_state = TodoExecutionResumeState(
        run_id="review-run-1",
        plan=other_plan,
        updated_at=datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc),
    )

    try:
        asyncio.run(TodoExecutionRunner(executor).run(plan, resume_state=resume_state))
    except ValueError as exc:
        assert str(exc) == "Todo runner resume_state.plan must match the plan being run."
    else:
        raise AssertionError("Expected mismatched resume_state plan to fail.")


def test_todo_execution_runner_emits_lifecycle_events_for_retry_then_success() -> None:
    attempts_by_id: dict[str, int] = {}
    events: list[tuple[str, dict]] = []

    async def executor(task) -> TodoTaskResult:
        attempts_by_id[task.id] = attempts_by_id.get(task.id, 0) + 1
        if attempts_by_id[task.id] < 2:
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

    results = asyncio.run(
        TodoExecutionRunner(
            executor,
            max_retries=2,
            event_handler=lambda event_name, payload: events.append(
                (event_name, dict(payload))
            ),
        ).run(plan)
    )

    assert results == [
        TodoTaskResult(
            id="extract_fees",
            status=TodoTaskStatus.SUCCEEDED,
            result={"summary": "Fee facts extracted after retry."},
        )
    ]
    assert [event_name for event_name, _ in events] == [
        TODO_EVENT_LAYER_STARTED,
        TODO_EVENT_TASK_STARTED,
        TODO_EVENT_TASK_FAILED,
        TODO_EVENT_TASK_RETRYING,
        TODO_EVENT_TASK_STARTED,
        TODO_EVENT_TASK_SUCCEEDED,
    ]
    assert events[2][1]["error_type"] == "transient_failure"
    assert events[2][1]["duration_ms"] is not None
    assert events[3][1]["attempt"] == 1
    assert events[3][1]["next_attempt"] == 2
    assert events[5][1]["result_keys"] == ["summary"]


def test_todo_execution_runner_emits_failure_and_dependency_skip_events() -> None:
    events: list[tuple[str, dict]] = []

    async def executor(task) -> TodoTaskResult:
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

    results = asyncio.run(
        TodoExecutionRunner(
            executor,
            max_retries=0,
            event_handler=lambda event_name, payload: events.append(
                (event_name, dict(payload))
            ),
        ).run(plan)
    )

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
    assert [event_name for event_name, _ in events] == [
        TODO_EVENT_LAYER_STARTED,
        TODO_EVENT_TASK_STARTED,
        TODO_EVENT_TASK_FAILED,
        TODO_EVENT_LAYER_STARTED,
        TODO_EVENT_TASK_SKIPPED,
    ]
    assert events[-1][1]["failed_dependency_task_id"] == "extract_fees"
