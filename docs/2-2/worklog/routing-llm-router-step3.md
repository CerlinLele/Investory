# Routing LLM Router Worklog

## Step 3 - Add Optional LLM Router

Timestamp: 2026-05-31T23:35:44.8101745+10:00

Plan source: the routing project-placement Markdown file under `docs/2-2`.

Actions:

- Added `LearningEntryRoute`, `LearningEntryRouteDecision`, and `LearningEntryLLMRouter` for structured LLM routing output.
- Added the `flows/learning_entry_router.md` prompt for unresolved learning-entry routing.
- Wired `InvestoryPolicyGate` to call an injected `llm_router` only when deterministic rules cannot infer a candidate task type and required-input/policy gates have not already returned.
- Kept the default behavior unchanged when no LLM router is configured: unresolved payloads still ask for missing input.
- Exposed optional `llm_router` injection through `LearningEntryFlow` and `build_learning_entry_flow()`.
- Added tests that verify deterministic rule routes do not call the LLM router, unresolved payloads can be routed by an injected router, missing/refusal LLM routes map to existing policy actions, and the concrete LLM router uses `LearningEntryRouteDecision` as the structured output model.

Files touched:

- `src/investory/agent_core/runtime/flow/learning_entry_router.py`
- `src/investory/agent_core/prompts/flows/learning_entry_router.md`
- `src/investory/agent_core/runtime/flow/investory_policy_gate.py`
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- `tests/test_investory_policy_gate.py`
- `tests/test_learning_entry_router.py`
- `docs/2-2/worklog/routing-llm-router-step3.md`

Verification:

- `pytest tests\test_learning_entry_rules.py tests\test_investory_policy_gate.py` -> 22 passed, 1 existing pydantic warning.
- `.venv\Scripts\python.exe -m pytest tests\test_learning_entry_router.py` -> 1 passed.
- `.venv\Scripts\python.exe -m pytest tests\test_learning_entry_flow.py tests\test_learning_entry_router.py tests\test_investory_policy_gate.py tests\test_learning_entry_rules.py` -> 32 passed.
- `python -m py_compile src\investory\agent_core\runtime\flow\learning_entry_router.py src\investory\agent_core\runtime\flow\investory_policy_gate.py src\investory\agent_core\runtime\flow\learning_entry_flow.py tests\test_learning_entry_router.py tests\test_investory_policy_gate.py` -> passed.

Result:

- Step 3 is implemented within the plan boundary. LLM routing is available as an optional injected component and is only used after deterministic rule routing cannot decide a task.
