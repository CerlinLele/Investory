# Routing Policy Gate Worklog

## Step 1 - Unify Policy Gate

Timestamp: 2026-05-31T23:06:48.6200089+10:00

Plan source: the routing project-placement Markdown file under `docs/2-2`.

Actions:

- Updated `src/investory/agent_core/runtime/flow/learning_entry_flow.py` so the first graph node evaluates `InvestoryPolicyGate.evaluate()` through `InvestoryPolicyInput`.
- Routed policy-gate actions to existing learning-entry outcomes:
  - `ask_for_missing_input` -> missing-input result.
  - `refuse_and_redirect` -> refusal result.
  - `execute_learning_task` -> task spec resolution and executor call.
- Removed duplicated missing-field and investment-advice checks from `LearningEntryFlow`; those decisions now come from `InvestoryPolicyGate`.
- Added flow tests for policy-gate branches that were previously not exercised by the flow: unsupported realtime data and required confirmation.

Files touched:

- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- `tests/test_learning_entry_flow.py`
- `docs/2-2/worklog/routing-policy-gate-step1.md`

Verification:

- `pytest tests\test_investory_policy_gate.py` -> 5 passed, 1 existing pydantic warning.
- `python -m py_compile src\investory\agent_core\runtime\flow\learning_entry_flow.py tests\test_learning_entry_flow.py` -> passed.
- `pytest tests\test_learning_entry_flow.py tests\test_investory_policy_gate.py` -> blocked during collection because the current Python environment does not have `langgraph` installed.

Result:

- Step 1 is implemented within the plan boundary. `/learning-entry` now reuses the centralized policy gate for missing input, direct investment advice refusal, realtime-data gating, and user-confirmation gating before task execution.
