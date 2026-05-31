# Routing Rule Routing Worklog

## Step 2 - Preserve Rule Routing

Timestamp: 2026-05-31T23:22:10.3192270+10:00

Plan source: the routing project-placement Markdown file under `docs/2-2`.

Actions:

- Kept `infer_candidate_task_type()` as the deterministic rule-routing source inside `InvestoryPolicyGate.evaluate()`.
- Added `CANDIDATE_TASK_TYPE_METADATA_KEY` so the rule-routing metadata key is a named constant instead of a repeated raw string.
- Updated `LearningEntryFlow` to read the candidate task type through the shared metadata constant.
- Added policy-gate tests proving complete QA, summary, and brief payload shapes route to execution with the expected candidate task type.

Files touched:

- `src/investory/agent_core/runtime/flow/investory_policy_gate.py`
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- `tests/test_investory_policy_gate.py`
- `docs/2-2/worklog/routing-rule-routing-step2.md`

Verification:

- `pytest tests\test_learning_entry_rules.py tests\test_investory_policy_gate.py` -> 18 passed, 1 existing pydantic warning.
- `python -m py_compile src\investory\agent_core\runtime\flow\investory_policy_gate.py src\investory\agent_core\runtime\flow\learning_entry_flow.py tests\test_investory_policy_gate.py` -> passed.

Result:

- Step 2 is implemented within the plan boundary. The learning-entry policy gate still uses deterministic field-shape routing before any future LLM router path, and the QA, summary, and brief route decisions are covered by tests.
