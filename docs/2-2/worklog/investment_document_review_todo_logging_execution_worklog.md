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

