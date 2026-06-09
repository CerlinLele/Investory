# Investment Document Review To-Do Logging Execution Worklog

Plan source: `docs/2-2/investment_document_review_todo_logging_plan.md`

## Phase 1 - 接入基础日志配置

Timestamp: 2026-06-09T16:40:12.4257462+10:00

Actions:

- Added a reusable logging setup module that configures console and file logging through Python standard `logging`.
- Added `INVESTORY_LOG_LEVEL` support to `AppConfig`, defaulting to `INFO`.
- Wired logging setup into FastAPI app creation so app startup creates and writes `logs/investory.log`.
- Added tests for log level config loading, file log creation, and invalid log level rejection.
- Added `logs/*.log` to `.gitignore` so generated runtime logs do not appear as source changes while keeping `logs/.gitkeep`.

Files touched:

- `.gitignore`
- `src/investory/config.py`
- `src/investory/logging_config.py`
- `src/investory/main.py`
- `tests/test_config.py`
- `tests/test_logging_config.py`
- `docs/2-2/worklog/investment_document_review_todo_logging_execution_worklog.md`

Evidence:

- `src/investory/logging_config.py:24` defines `configure_logging()` for console and file logging.
- `src/investory/logging_config.py:9` defines the runtime log filename as `investory.log`.
- `src/investory/config.py:72` adds `AppConfig.log_level`.
- `src/investory/config.py:158` reads `INVESTORY_LOG_LEVEL` and normalizes it to uppercase.
- `src/investory/main.py:29` calls `configure_logging()` during `create_app()`.
- `.gitignore:22` ignores generated `logs/*.log` files.
- `tests/test_config.py:26` verifies `INVESTORY_LOG_LEVEL` loading.
- `tests/test_logging_config.py:20` verifies file logging writes a message.
- `tests/test_logging_config.py:36` verifies invalid log levels fail clearly.

Verification:

- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_config.py tests\test_logging_config.py tests\test_gateway_api.py`
- Result: 13 passed.

Notes:

- Running gateway tests now creates `logs/investory.log` as expected; it is ignored by Git.
- The implementation intentionally does not add To-Do plan or task lifecycle events yet. Those belong to Phase 2 and Phase 3.

## Phase 2 - Flow 级记录 To-Do plan

Timestamp: 2026-06-09T17:05:55.7348944+10:00

Actions:

- Added a module logger to `document_review_flow.py`.
- Added `_log_review_todo_plan_generated()` to emit a stable INFO log for generated To-Do plans and DEBUG logs for individual tasks.
- Added `_guess_review_plan_chunk_count()` so the emitted plan log can include chunk count for both chunk and LLM-generated plans.
- Wired the logger into both branches of `generate_review_todo_plan()` so successful plan creation now emits plan metadata before returning.
- Added a focused logging test that verifies the plan summary and task metadata are logged, while document text is not leaked.

Files touched:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
- `tests/test_investment_document_review_flow.py`
- `docs/2-2/worklog/investment_document_review_todo_logging_execution_worklog.md`

Evidence:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:66` creates the module logger.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:248` defines `_log_review_todo_plan_generated()`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:278` defines `_guess_review_plan_chunk_count()`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:534` logs chunk-path plan generation before returning.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:562` logs LLM-generated plan creation before returning.
- `tests/test_investment_document_review_flow.py:498` verifies the plan summary and task logs are emitted.

Verification:

- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py -k "generate_review_todo_plan_logs_plan_summary_and_tasks or generate_review_todo_plan_accepts_supported_document_type_frameworks or generate_review_todo_plan_node_builds_plan_without_executing_tasks"`
- Result: 3 passed, 20 deselected.

Notes:

- A pre-existing regression test in `tests/test_investment_document_review_flow.py:1722` now fails because it still expects a non-empty document to take the single-pass path, while the current flow routes non-empty documents through the chunk path.
- That failure is outside the new logging code and should be handled as a separate follow-up if you want the full file green again.

## Phase 3 - Runner 级记录任务生命周期

Timestamp: 2026-06-09T17:41:00+10:00

Actions:

- Extended `TodoExecutionRunner` skip events to surface `failed_dependency_task_id` in the emitted payload.
- Wired `InvestmentDocumentReviewFlow._build_todo_execution_runner()` to pass a flow-specific runner event handler into `TodoExecutionRunner`.
- Added flow-side event mapping for `todo.layer.started`, `todo.task.started`, `todo.task.retrying`, `todo.task.succeeded`, `todo.task.failed`, and `todo.task.skipped`.
- Added runner-level tests to cover lifecycle event emission for retry, success, failure, and dependency-driven skip cases.
- Added a flow-level logging test to confirm `execute_review_todo_plan()` emits lifecycle logs without leaking document text.
- Ran the new runner lifecycle test subset once, found that the actual event sequence emits `todo.task.failed` before `todo.task.retrying`, then updated the test expectation to match the runner's real behavior and reran the subset.

Files touched:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
- `src/investory/agent_core/runtime/todo_core/runner.py`
- `tests/test_todo_execution_runner.py`
- `tests/test_investment_document_review_flow.py`
- `docs/2-2/worklog/investment_document_review_todo_logging_execution_worklog.md`

Evidence:

- `src/investory/agent_core/runtime/todo_core/runner.py:315` now includes `failed_dependency_task_id` in skipped task payloads.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:302` maps runner events to flow log messages.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:864` injects the event handler into `TodoExecutionRunner`.
- `tests/test_todo_execution_runner.py:643` adds lifecycle event coverage for retry/success and failure/skip flows.
- `tests/test_investment_document_review_flow.py:683` adds a flow-level lifecycle logging assertion.

Verification:

- Command: `& .\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py -k "lifecycle_events_for_retry_then_success or failure_and_dependency_skip_events or skips_downstream_task_after_retry_exhaustion"`
- First result: 1 failed, 2 passed, 9 deselected.
- Failure detail: `test_todo_execution_runner_emits_lifecycle_events_for_retry_then_success` expected retry to be emitted directly after `todo.task.started`, but the runner correctly emits `todo.task.failed` first and then `todo.task.retrying`.
- Command: `& .\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py -k "lifecycle_events_for_retry_then_success or failure_and_dependency_skip_events or skips_downstream_task_after_retry_exhaustion"`
- Result: 3 passed, 9 deselected.
- Command: `& .\.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py -k "logs_runner_lifecycle or uses_todo_execution_runner or loads_and_saves_resume_state_slot"`
- Result: 3 passed, 21 deselected.

## Phase 4 - Execution summary and resume logging

Timestamp: 2026-06-09T18:47:22+10:00

Actions:

- Added flow-level execution summary logging around `TodoExecutionRunner.run()`.
- Added `investment_document_review.todo_execution.started` with `session_id`, `task_count`, `resume_task_count`, and `failure_policy`.
- Added `investment_document_review.todo_execution.completed` with succeeded/failed/skipped counts, execution duration, and whether synthesis output was produced.
- Added resume visibility logs for successful resume state load and save.
- Added focused flow tests for execution summary logs and resume load/save logs.
- Ran the Phase 4 flow test subset once, found the test expected the wrong default `failure_policy`, then updated the assertion to match the actual default value `retry_then_fail` and reran successfully.
- Reran the Phase 3 runner lifecycle subset to confirm runner event logging still passes after the Phase 4 flow summary changes.

Files touched:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
- `tests/test_investment_document_review_flow.py`
- `docs/2-2/worklog/investment_document_review_todo_logging_execution_worklog.md`

Evidence:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:376` defines `_count_todo_results_by_status()`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:390` defines `_log_review_todo_execution_started()`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:406` defines `_log_review_todo_execution_completed()`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:810` logs execution start after resume state is loaded.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:826` logs execution completion after runner results are available and before resume state is saved.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:874` logs successful resume load.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:905` logs successful resume save.
- `tests/test_investment_document_review_flow.py:683` verifies execution start/completion summary logs.
- `tests/test_investment_document_review_flow.py:773` verifies resume load/save logs.

Verification:

- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py -k "logs_runner_lifecycle or loads_and_saves_resume_state_slot or includes_resumed_completed_results_in_synthesis_once"`
- First result: 1 failed, 2 passed, 21 deselected.
- Failure detail: `test_execute_review_todo_plan_logs_runner_lifecycle` expected `failure_policy=skip_dependents_on_failure`, while the actual default plan policy is `failure_policy=retry_then_fail`.
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py -k "logs_runner_lifecycle or loads_and_saves_resume_state_slot or includes_resumed_completed_results_in_synthesis_once"`
- Result: 3 passed, 21 deselected.
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py -k "lifecycle_events_for_retry_then_success or failure_and_dependency_skip_events or skips_downstream_task_after_retry_exhaustion"`
- Result: 3 passed, 9 deselected.

Notes:

- `todo_execution.completed` is intentionally emitted before resume state is saved so runner results remain visible even if a later resume-store save fails.
- The unrelated working-tree deletion of `logs/.gitkeep` was observed but not touched as part of Phase 4.

## Phase 5 - Test baseline and Apifox log guidance

Timestamp: 2026-06-09T19:01:58+10:00

Actions:

- Ran the plan's recommended full pytest command for `tests/test_todo_execution_runner.py` and `tests/test_investment_document_review_flow.py`.
- Investigated the single failing flow test and confirmed it still encoded the old single-pass assumption rather than the current chunk-review execution path.
- Updated the outdated test to assert the current chunk-path behavior: repeated extract failures now surface as a synthesize-stage structured output failure after retries are exhausted.
- Added a `服务端日志观察点` section to the Apifox test plan so manual testers know where to read `logs/investory.log`, which event names to grep for, and how to interpret success, failure, multi-chunk, and resume scenarios.
- Reran the same full pytest command after the test/doc updates and confirmed the suite is fully green.

Files touched:

- `tests/test_investment_document_review_flow.py`
- `docs/2-2/investment_document_review_apifox_test_plan.md`
- `docs/2-2/worklog/investment_document_review_todo_logging_execution_worklog.md`

Evidence:

- `tests/test_investment_document_review_flow.py:1836` now verifies the chunk-review failure outcome instead of expecting the old single-pass error passthrough.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:658` routes any non-empty `document_chunks` state into the To-Do plan path.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:849` emits the `Chunk-based document review did not produce synthesis.` fallback error when chunk execution never produces a synthesize result.
- `docs/2-2/investment_document_review_apifox_test_plan.md:61` adds the new `服务端日志观察点` section.
- `docs/2-2/investment_document_review_apifox_test_plan.md:86` documents how to inspect failure logs via `todo_task.failed`.
- `docs/2-2/investment_document_review_apifox_test_plan.md:101` documents how to read `todo_execution.completed` as the request-level completion summary.

Verification:

- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py tests\test_investment_document_review_flow.py`
- First result: 1 failed, 35 passed.
- Failure detail: `test_document_review_flow_preserves_downstream_executor_error_result` still expected the legacy single-pass executor error to be returned directly, but the current implementation routes non-empty document text through the chunk To-Do path and returns a synthesize-stage structured output failure when extraction never succeeds.
- Code/test change: renamed the test to `test_document_review_flow_returns_chunk_synthesis_error_when_extract_never_succeeds` and updated the assertions to match the current chunk execution semantics and retry behavior.
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py tests\test_investment_document_review_flow.py`
- Result: 36 passed.

Notes:

- This Phase 5 change did not alter runtime logging behavior; it aligned the remaining full-suite test with the already-shipped chunk review routing semantics and improved operator-facing test documentation.
- The unrelated working-tree deletion of `logs/.gitkeep` remained untouched during Phase 5 as well.
