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
