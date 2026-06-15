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

## 2026-06-01T02:18:56.0893029+10:00 Phase 3

- Step: Phase 3 - 实现拓扑分层
- Action: Added dependency layering module at `src/investory/agent_core/runtime/todo_core/dependency_layers.py`.
- Files touched:
  - `src/investory/agent_core/runtime/todo_core/dependency_layers.py`
- Result:
  - Added `build_dependency_layers(plan)` returning `list[list[TodoTaskSpec]]`.
  - Enforced upfront validation via `ensure_valid_todo_plan(plan)`.
  - Implemented layered topological scheduling by dependency count:
    - same-layer tasks are all tasks whose unresolved dependencies are zero at that layer
    - next layer is unlocked only after current layer is fully resolved
  - Preserved deterministic ordering inside each layer using original task order.
  - Added defensive unresolved-task guard to prevent partial layering output.
- Evidence anchors:
  - `src/investory/agent_core/runtime/todo_core/dependency_layers.py:5`
  - `src/investory/agent_core/runtime/todo_core/dependency_layers.py:6`
  - `src/investory/agent_core/runtime/todo_core/dependency_layers.py:44`
  - Command evidence: `.\.venv\Scripts\python.exe -m py_compile src\investory\agent_core\runtime\todo_core\dependency_layers.py` (pass)

## 2026-06-01T02:23:31.1339308+10:00 Phase 4

- Step: Phase 4 - 实现 fake executor runner
- Action: Added async todo execution runner at `src/investory/agent_core/runtime/todo_core/runner.py`.
- Files touched:
  - `src/investory/agent_core/runtime/todo_core/runner.py`
- Result:
  - Added `TodoTaskExecutor = Callable[[TodoTaskSpec], Awaitable[TodoTaskResult]]`.
  - Added `TodoExecutionRunner.run(plan)` with flow:
    - `ensure_valid_todo_plan(plan)`
    - `build_dependency_layers(plan)`
    - execute per layer with same-layer `asyncio.gather(...)`
    - apply failure policy behavior and collect full results
  - Added configurable concurrency limit via `DEFAULT_TODO_CONCURRENCY = 3`.
  - Added retry behavior for `RETRY_THEN_FAIL` (`max_retries` configurable).
  - Added policy handling:
    - `FAIL_FAST`: stop scheduling later tasks after a failure; later tasks marked skipped.
    - `BEST_EFFORT`: continue runnable tasks; tasks with failed dependencies marked skipped.
    - `RETRY_THEN_FAIL`: retry failed tasks before final failure; dependent failures propagate to skipped.
  - Ensured result list is complete and returned in original plan order.
- Evidence anchors:
  - `src/investory/agent_core/runtime/todo_core/runner.py:18`
  - `src/investory/agent_core/runtime/todo_core/runner.py:37`
  - `src/investory/agent_core/runtime/todo_core/runner.py:54`
  - `src/investory/agent_core/runtime/todo_core/runner.py:89`
  - `src/investory/agent_core/runtime/todo_core/runner.py:104`
  - `src/investory/agent_core/runtime/todo_core/runner.py:119`
  - `src/investory/agent_core/runtime/todo_core/runner.py:195`
  - Command evidence: `.\.venv\Scripts\python.exe -m py_compile src\investory\agent_core\runtime\todo_core\runner.py` (pass)
