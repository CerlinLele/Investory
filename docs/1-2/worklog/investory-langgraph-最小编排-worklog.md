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
