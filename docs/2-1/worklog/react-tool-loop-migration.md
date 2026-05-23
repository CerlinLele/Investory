# ReAct tool loop migration worklog

## Step 0: 固定当前行为基线

Timestamp: 2026-05-23 23:22:32 +10:00

Plan file: `docs/2-1/Investory_第06课_ReAct工具调用回路_项目迁移笔记.md`

Actions:

- Ran baseline test command from the plan:

```powershell
python -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

Files touched:

- `docs/2-1/worklog/react-tool-loop-migration.md`

Files checked by the planned baseline command:

- `tests/test_task_execution_pipeline.py`
- `tests/test_learning_qa_orchestration_flow.py`
- `tests/test_learning_qa_decision_planner.py`
- `tests/test_action_router.py`
- `tests/test_action_executors.py`

Result:

- Blocked during pytest collection before behavioral assertions ran.
- All five selected test modules failed to import because the active Python environment does not have `langchain_core` installed.

Evidence:

- Import anchor: `src/investory/agent_core/runtime/message_builder.py:4` imports `ChatPromptTemplate` from `langchain_core.prompts`.
- Dependency anchor: `pyproject.toml` declares `langchain==1.3.1` and `langchain-openai==1.2.1`.
- Lockfile anchor: `requirements.lock.txt` includes `langchain-core==1.4.0`.
- Pytest error: `ModuleNotFoundError: No module named 'langchain_core'`.

Minimal unblock action:

- Install the project dependencies into the active Python environment, then rerun the same Step 0 baseline command.

Follow-up timestamp: 2026-05-23 23:26:14 +10:00

Unblock action:

- Confirmed the project virtual environment exists at `.venv/Scripts/python.exe`.
- Confirmed `.venv` has `langchain_core==1.4.0`.
- Reran the same Step 0 baseline tests with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

Follow-up result:

- Passed: `32 passed in 2.37s`.
- Step 0 acceptance criteria met using the project virtual environment.

## Step 1: 新增工具契约

Timestamp: 2026-05-23 23:33:03 +10:00

Actions:

- Added the tool package entrypoint.
- Added minimal tool contract models and protocol.
- Added focused contract tests for serialization, call records, and structural protocol compatibility.

Files touched:

- `src/investory/agent_core/tools/__init__.py`
- `src/investory/agent_core/tools/contracts.py`
- `tests/test_tool_contracts.py`
- `docs/2-1/worklog/react-tool-loop-migration.md`

Contract boundaries:

- `ToolSource`, `ToolCallRecord`, `ToolExecutionError`, and `ToolExecutor` are independent of LangChain, LangGraph, and FastAPI.
- Runtime dependencies are limited to the standard library typing module and Pydantic.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_contracts.py -q
```

Result: `4 passed in 0.04s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

Result: `32 passed in 1.82s`.

Evidence:

- `ToolSource` serialization is covered by `tests/test_tool_contracts.py`.
- `ToolCallRecord` success and failure records are covered by `tests/test_tool_contracts.py`.
- `ToolExecutor` structural compatibility is covered by `tests/test_tool_contracts.py`.
- Existing Step 0 baseline remained green after adding the tool contract layer.

## Step 2: 新增 Tool Registry

Timestamp: 2026-05-23 23:55:32 +10:00

Actions:

- Added `ToolRegistry` as the centralized lookup and registration surface for tools.
- Added `UnknownToolError` for missing tool lookups.
- Exported registry types from the tool package entrypoint.
- Added focused registry tests for registration, initial tools, sorted listing, unknown tools, and duplicate-name override behavior.

Files touched:

- `src/investory/agent_core/tools/__init__.py`
- `src/investory/agent_core/tools/registry.py`
- `tests/test_tool_registry.py`
- `docs/2-1/worklog/react-tool-loop-migration.md`

Registry behavior:

- `ToolRegistry` stores tools by `tool.name`.
- `get(name)` returns the registered tool or raises `UnknownToolError`.
- `list_names()` returns sorted tool names.
- Duplicate registration currently overrides the prior tool, matching the Step 2 plan.
- The registry only manages tools; it does not execute them.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py tests/test_tool_contracts.py -q
```

Result: `9 passed in 0.06s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

Result: `32 passed in 1.90s`.

Evidence:

- Registry lookup and registration are covered by `tests/test_tool_registry.py`.
- Unknown tool failure is covered by `tests/test_tool_registry.py`.
- Duplicate-name override behavior is explicitly covered by `tests/test_tool_registry.py`.
- Existing Step 0 baseline remained green after adding the registry layer.

## Step 3: 新增第一批 Mock Tools

Timestamp: 2026-05-24 01:03:20 +10:00

Actions:

- Added mock `lookup_financial_concept`.
- Added mock `lookup_instrument_profile`.
- Added mock `extract_learning_material_facts`.
- Added `build_mock_tool_registry()` to package the first mock tools.
- Exported the mock tool models, tool classes, and registry builder from the tool package entrypoint.
- Added focused tests for stable mock output, source metadata, uncertainty handling, advice-neutral wording, and registry packaging.

Files touched:

- `src/investory/agent_core/tools/__init__.py`
- `src/investory/agent_core/tools/financial_concepts.py`
- `src/investory/agent_core/tools/instrument_profile.py`
- `src/investory/agent_core/tools/material_extraction.py`
- `src/investory/agent_core/tools/mocks.py`
- `tests/test_financial_concept_tool.py`
- `tests/test_instrument_profile_tool.py`
- `tests/test_material_extraction_tool.py`
- `docs/2-1/worklog/react-tool-loop-migration.md`

Mock tool boundaries:

- All tools are read-only and deterministic.
- No tool depends on network access.
- Outputs include `uncertainty`.
- Data-bearing outputs include `ToolSource` metadata with `provider` and `as_of`.
- Tool text avoids buy, sell, hold, suitability, and allocation conclusions.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_financial_concept_tool.py tests/test_instrument_profile_tool.py tests/test_material_extraction_tool.py -q
```

Result: `10 passed in 0.09s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tool_contracts.py tests/test_tool_registry.py -q
```

Result: `9 passed in 0.08s`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

Result: `32 passed in 2.03s`.

Evidence:

- Known and unknown concept lookup are covered by `tests/test_financial_concept_tool.py`.
- Known and unknown instrument profile lookup are covered by `tests/test_instrument_profile_tool.py`.
- Material fact extraction and empty-material uncertainty are covered by `tests/test_material_extraction_tool.py`.
- Mock registry packaging is covered by `tests/test_financial_concept_tool.py`.
- Existing Step 0 baseline remained green after adding the mock tool layer.
