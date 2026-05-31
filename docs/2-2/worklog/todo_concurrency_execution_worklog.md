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
