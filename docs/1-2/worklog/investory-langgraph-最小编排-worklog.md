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
  - `candidate_task_type` is limited by `LearningEntryCandidateTaskType`.
  - `decision` is limited by `LearningEntryDecision`.
  - The new state contract is exported through `investory.agent_core.contracts`.

## 2026-05-28 17:53:18 +10:00 - Step 3. 实现本地规则层

- Action: Added deterministic learning entry rule helpers to `src/investory/agent_core/runtime/flow/learning_entry_rules.py`.
- Files touched:
  - `src/investory/agent_core/runtime/flow/learning_entry_rules.py`
  - `docs/1-2/worklog/investory-langgraph-最小编排-worklog.md`
- Result: The future learning entry flow can locally detect obvious missing fields and infer a candidate learning task before any LLM policy decision.
- Evidence:
  - `detect_missing_fields(payload)` returns missing `material_text`, `source_material`, or `instrument_name_or_code` when the provided fields imply a known task but required input is absent.
  - `infer_candidate_task_type(payload)` returns `LearningEntryCandidateTaskType.QA`, `SUMMARY`, `BRIEF`, or `None`.
  - Field names are defined as module-level constants instead of inline string literals.

## 2026-05-28 18:05:06 +10:00 - Step 4. 定义“投资建议判断”结构化输出

- Action: Added a structured policy decision model and flow prompt for learning entry investment-advice classification.
- Files touched:
  - `src/investory/agent_core/runtime/flow/learning_entry_decision.py`
  - `src/investory/agent_core/prompts/flows/learning_entry_decision.md`
  - `docs/1-2/worklog/investory-langgraph-最小编排-worklog.md`
- Result: The future policy node has a narrow structured output contract focused only on refusing direct investment advice or allowing a learning task to continue.
- Evidence:
  - `LearningEntryPolicyDecision.route_action` uses the existing `LearningEntryDecision` enum.
  - `POLICY_ROUTE_ACTIONS` limits policy output to `refuse_and_redirect` or `execute_learning_task`.
  - The prompt explicitly excludes missing-field detection, task type mapping, final answer generation, and investment advice.
