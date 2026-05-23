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
