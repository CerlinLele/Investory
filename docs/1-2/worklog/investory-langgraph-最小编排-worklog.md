# Investory LangGraph 最小编排 Worklog

## 2026-05-28 17:16:55 +10:00 - Step 1. 定义新的 gateway request schema

- Action: Added `LearningEntryRequest` to `src/investory/gateway/schemas.py`.
- Files touched:
  - `src/investory/gateway/schemas.py`
  - `docs/1-2/worklog/investory-langgraph-最小编排-worklog.md`
- Result: The gateway now has a dedicated generic request schema for the future `/learning-entry` orchestration endpoint, while the existing `TaskRequest` and `TaskResponse` contracts remain unchanged.
- Evidence:
  - `LearningEntryRequest` defines `payload: dict[str, Any]`.
  - `LearningEntryRequest` defines `session_id: NonEmptyString | None = None`.
  - `LearningEntryRequest` is exported through `__all__`.

## 2026-05-28 17:21:44 +10:00 - Step 2. 定义 LangGraph 专用 state

- Action: Added `LearningEntryState` to `src/investory/agent_core/contracts/learning_entry_state.py`.
- Files touched:
  - `src/investory/agent_core/contracts/learning_entry_state.py`
  - `src/investory/agent_core/contracts/__init__.py`
  - `docs/1-2/worklog/investory-langgraph-最小编排-worklog.md`
- Result: The agent contracts now include a dedicated state model for the future learning entry flow, separate from the existing task execution `TaskFlowState`.
- Evidence:
  - `LearningEntryState` stores `session_id` and `input_payload`.
  - `missing_fields` uses a default empty list.
  - `decision` is limited to `ask_for_missing_input`, `refuse_and_redirect`, or `execute_learning_task`.
  - The new state contract is exported through `investory.agent_core.contracts`.
