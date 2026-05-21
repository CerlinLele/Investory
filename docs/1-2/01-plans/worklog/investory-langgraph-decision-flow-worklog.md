# Investory LangGraph Decision Flow Worklog

## Step 0.1 Baseline Snapshot

- Timestamp: 2026-05-22 05:33:01 +10:00
- Action:
  - Ran baseline test command 1 in venv:
    - `.venv\Scripts\python.exe -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
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
    - `.venv\Scripts\python.exe -m pytest tests/test_decision_flow.py -q`
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
  - Split `DecisionFlow` sequential logic into 4 node-style methods:
    - `classify_request`
    - `validate_decision_contract`
    - `execute_routed_action` (temporary aggregate execution node)
    - `build_task_response`
  - Kept `run(...)` as linear orchestration that invokes these methods in order.
  - Ran validation tests:
    - `.venv\Scripts\python.exe -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q`
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
