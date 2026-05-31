# To-Do Concurrency Execution Worklog

## 2026-06-01T00:00:00+10:00 Phase 1

- Step: Phase 1 - 新增 To-Do 合约
- Action: Added contract models and enums in `src/investory/agent_core/contracts/todo_execution.py`.
- Files touched:
  - `src/investory/agent_core/contracts/todo_execution.py`
- Result:
  - Added `TodoTaskKind`, `TodoTaskStatus`, `TodoFailurePolicy` as `str, Enum`.
  - Added `TodoTaskSpec`, `TodoExecutionPlan`, `TodoTaskResult`.
  - List defaults use `Field(default_factory=list)`.
- Evidence anchors:
  - `src/investory/agent_core/contracts/todo_execution.py:25`
  - `src/investory/agent_core/contracts/todo_execution.py:32`
  - `src/investory/agent_core/contracts/todo_execution.py:40`
  - `src/investory/agent_core/contracts/todo_execution.py:46`
  - `src/investory/agent_core/contracts/todo_execution.py:56`
  - `src/investory/agent_core/contracts/todo_execution.py:62`

## 2026-06-01T02:02:16.6822959+10:00 Phase 2

- Step: Phase 2 - 实现计划校验
- Action: Added todo plan validation module at `src/investory/agent_core/runtime/todo_core/plan_validator.py`.
- Files touched:
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py`
- Result:
  - Added `TodoPlanValidationErrorCode` with `DUPLICATE_TASK_ID`, `UNKNOWN_DEPENDENCY`, `SELF_DEPENDENCY`, `CYCLE_DETECTED`, `EMPTY_DESCRIPTION`, `EMPTY_COMPLETION_CRITERIA`.
  - Added structured `TodoPlanValidationError` and `TodoPlanValidationResult`.
  - Implemented `validate_todo_plan(plan)` for duplicate id, unknown dependency, self dependency, description/completion checks, and cycle detection.
  - Added `ensure_valid_todo_plan(plan)` and `TodoPlanValidationException` for fail-fast integration in future runner.
  - Verified syntax with `.venv` Python compile.
- Evidence anchors:
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:9`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:18`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:26`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:31`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:47`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:136`
  - `src/investory/agent_core/runtime/todo_core/plan_validator.py:142`
  - Command evidence: `.\.venv\Scripts\python.exe -m py_compile src\investory\agent_core\runtime\todo_core\plan_validator.py` (pass)
