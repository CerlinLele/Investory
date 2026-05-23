# Investory LangGraph Decision Flow Worklog

## Step 0.1 Baseline Snapshot

- Timestamp: 2026-05-22 05:33:01 +10:00
- Action:
  - Ran baseline test command 1 in venv:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
  - Ran baseline test command 2 in venv:
    - `.venv\Scripts\python.exe -m pytest tests/test_task_executor.py tests/test_task_execution_pipeline.py -q`
- Files touched:
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Command 1 passed: `19 passed in 1.89s`
  - Command 2 passed: `13 passed in 0.25s`
  - Baseline behavior is stable under project venv.

## Step 0.2 Dependency Preparation

- Timestamp: 2026-05-22 05:38:49 +10:00
- Action:
  - Updated dependency pin in `pyproject.toml`:
    - `langgraph==1.1.10` -> `langgraph==1.2.1` (latest requested)
  - Ran install in venv:
    - `.venv\Scripts\python.exe -m pip install -e .[dev]`
  - Ran import verification:
    - `.venv\Scripts\python.exe -c "from langgraph.graph import StateGraph, START, END; print('ok')"`
  - Checked installed versions:
    - `.venv\Scripts\python.exe -c "import importlib.metadata as m; print(m.version('langgraph')); print(m.version('langchain'))"`
- Files touched:
  - `pyproject.toml`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Install failed with resolver conflict:
    - project pin requires `langgraph==1.2.1`
    - current project pin keeps `langchain==1.2.15`, which requires `langgraph<1.2.0,>=1.1.5`
  - Import check still passed because venv remains on:
    - `langgraph==1.1.10`
    - `langchain==1.2.15`
  - `requirements.lock.txt` was not refreshed to avoid writing an inconsistent lock.

### Step 0.2 Retry (latest-compatible resolution)

- Timestamp: 2026-05-22 05:41:35 +10:00
- Action:
  - Updated dependency pin in `pyproject.toml`:
    - `langchain==1.2.15` -> `langchain==1.3.1`
  - Re-ran install in venv:
    - `.venv\Scripts\python.exe -m pip install -e .[dev]`
  - Re-ran import verification:
    - `.venv\Scripts\python.exe -c "from langgraph.graph import StateGraph, START, END; print('ok')"`
  - Refreshed lock:
    - `.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt`
  - Verified installed versions:
    - `langchain=1.3.1`
    - `langgraph=1.2.1`
    - `langchain-openai=1.2.1`
- Files touched:
  - `pyproject.toml`
  - `requirements.lock.txt`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Dependency resolution succeeded with latest requested `langgraph==1.2.1`.
  - `StateGraph`, `START`, `END` import check passed.
  - Lock is now consistent with venv-installed versions.

## Step 1.1 Fix State Object

- Timestamp: 2026-05-22 05:48:08 +10:00
- Action:
  - Renamed flow state model:
    - `DecisionFlowState` -> `LearningQaFlowState`
  - Kept backward-compatible alias:
    - `DecisionFlowState = LearningQaFlowState`
  - Updated flow internals to use new state name for:
    - `last_state` type annotation
    - state construction in `run(...)`
  - Ran validation test:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Behavior unchanged for Step 1.1 scope.
  - `last_state` remains observable after `run(...)`.
  - Test passed: `5 passed in 1.59s`.

## Step 1.2 Split Main Nodes (Minimal Set)

- Timestamp: 2026-05-22 05:53:41 +10:00
- Action:
  - Split `LearningQaOrchestrationFlow` sequential logic into 4 node-style methods:
    - `classify_request`
    - `validate_decision_contract`
    - `execute_routed_action` (temporary aggregate execution node)
    - `build_task_response`
  - Kept `run(...)` as linear orchestration that invokes these methods in order.
  - Ran validation tests:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Behavior remains linear and unchanged for this layer.
  - `last_state` contract remains intact.
  - Tests passed: `19 passed in 1.71s`.

### Execution Decision Note

- Timestamp: 2026-05-22 06:06:22 +10:00
- Decision:
  - Continue graph-structure refactor first.
  - Defer adding `refuse_investment_advice` classification rules to Layer 2/3.
- Scope impact:
  - Step 1.x keeps current default planner behavior.
  - No new business classification logic is added in Step 1.2.

## Step 1.3 Compile Linear Graph

- Timestamp: 2026-05-22 14:00:27 +10:00
- Action:
  - Added linear `StateGraph` compilation in `LearningQaOrchestrationFlow`:
    - `START -> classify_request -> validate_decision_contract -> execute_routed_action -> build_task_response -> END`
  - Switched `run(...)` to:
    - build `initial_state`
    - `graph.invoke(initial_state)`
    - write `last_state`
    - return `output`
  - Added graph node adapters for the 4 main node methods.
  - Kept external signature unchanged:
    - `run(spec, payload, request_id=None) -> TaskResult`
  - Ran validation tests:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Linear graph execution is active via `graph.invoke(...)`.
  - `last_state` remains observable with final output/error.
  - Tests passed: `19 passed in 1.89s`.

## Step 2.1 Route Function

- Timestamp: 2026-05-22 15:20:38 +10:00
- Action:
  - Added route function:
    - `route_by_action_key(state: LearningQaFlowState) -> str`
  - Implemented routing key rules:
    - `state.action_call is None` -> `"build_task_response"`
    - otherwise -> `state.action_call.action`
  - Added route-function tests:
    - missing `action_call` returns `"build_task_response"`
    - present `action_call` returns action key (`"run_task_model"`)
  - Ran validation test:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `tests/test_learning_qa_orchestration_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Route-key behavior is explicit and test-covered.
  - Tests passed: `7 passed in 1.75s`.

## Step 3.2 Cleanup Transition Path

- Timestamp: 2026-05-22 18:19:16 +10:00
- Action:
  - Removed temporary transition method:
    - `execute_routed_action` (no longer used after action-specific node split).
  - Kept `run()` entry responsibilities unchanged:
    - build `initial_state`
    - `graph.invoke(initial_state)`
    - write `last_state`
    - return `output`
  - Ran validation tests:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Transition path cleanup completed.
  - `run()` remains a pure flow entry method.
  - Tests passed: `21 passed in 1.73s`.

## Error Convergence

- Timestamp: 2026-05-22 21:41:24 +10:00
- Action:
  - Added flow-level error convergence in `LearningQaOrchestrationFlow.run(...)`:
    - catches execution exceptions
    - converts them into failed `TaskResult`
    - writes `state.error` and `state.output`
    - persists `last_state` for observability
  - Added explicit convergence mapping:
    - `ActionValidationError` -> `TaskError(error_type="input_validation_failed", stage="input_validation")`
    - `ActionRoutingError` -> `TaskError(error_type="unknown_error", stage="model_call")`
    - all other exceptions -> `normalize_task_error(..., stage="model_call")`
  - Added tests for:
    - invalid action params convergence path
    - routing failure convergence path
  - Ran validation tests:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_action_validator.py -q`
- Files touched:
  - `src/investory/agent_core/runtime/decision_flow.py`
  - `tests/test_learning_qa_orchestration_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Exceptions in flow execution now converge into failed `TaskResult` outputs.
  - `last_state` remains available for both success and failure.
  - Tests passed: `22 passed in 1.63s`.

## Step 5.1 Test Coverage

- Timestamp: 2026-05-22 23:11:22 +10:00
- Action:
  - Enhanced `tests/test_learning_qa_orchestration_flow.py` coverage for Layer 5.1 supplement items:
    - added explicit compiled-graph check (`flow.graph` is invokable via `invoke`)
    - expanded `route_by_action_key` assertions to cover all 3 action keys:
      - `ask_missing_fields`
      - `run_task_model`
      - `refuse_investment_advice`
  - Kept existing branch-path coverage and failure-convergence coverage in place.
  - Ran Step 5.1 target tests in venv:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py -q`
  - Ran Step 5.2 regression subset in venv:
    - `.venv\Scripts\python.exe -m pytest tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
- Files touched:
  - `tests/test_learning_qa_orchestration_flow.py`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Step 5.1 coverage items are now explicitly asserted.
  - Decision flow test suite passed: `12 passed in 2.32s`.
  - Regression subset passed: `26 passed in 2.37s`.

## Step 5.3 Documentation Sync

- Timestamp: 2026-05-22 23:22:41 +10:00
- Action:
  - Updated orchestration scenario doc to align with current Decision Flow graph naming and structure:
    - `validate_decision_contract`
    - `route_by_action_key`
    - three action execution nodes
    - unified response build path
  - Added explicit scope boundary statements:
    - LangGraph is only used in orchestration flow layer
    - `TaskExecutor` remains the minimal execution unit
    - `TaskExecutionPipeline` remains internal to `TaskExecutor`
  - Updated smoke README with an "Orchestration Boundary" section to avoid mixing:
    - decision orchestration graph responsibilities
    - task smoke execution responsibilities
- Files touched:
  - `docs/1-2/investory-最小编排适用场景.md`
  - `src/investory/agent_core/runtime/smoke/README.md`
  - `docs/1-2/01-plans/worklog/investory-langgraph-decision-flow-worklog.md`
- Result:
  - Step 5.3 required documentation sync is complete and consistent with current runtime behavior.


