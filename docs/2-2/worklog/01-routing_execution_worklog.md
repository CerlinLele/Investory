# Routing Execution Worklog (Merged)

Plan source: the routing project-placement Markdown file under `docs/2-2`.

## Step 1 - Unify Policy Gate

Timestamp: 2026-05-31T23:06:48.6200089+10:00

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

## Step 2 - Preserve Rule Routing

Timestamp: 2026-05-31T23:22:10.3192270+10:00

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

## Step 3 - Add Optional LLM Router

Timestamp: 2026-05-31T23:35:44.8101745+10:00

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

## Step 4 - Add Low Confidence Fallback

Timestamp: 2026-06-01T00:23:47.3795151+10:00

Actions:

- Added `DEFAULT_ROUTE_CONFIDENCE_THRESHOLD = 0.6` to `InvestoryPolicyGate`.
- Added `InvestoryPolicyReason.LOW_CONFIDENCE_ROUTE` so low-confidence fallback is explicit instead of being merged into generic missing-input handling.
- Updated the LLM-route evaluation path so `confidence < 0.6` or `general_learning_clarification` returns a clarification fallback instead of executing a task.
- Kept the fallback action on the existing `ask_for_missing_input` branch so the HTTP/result contract does not need to change.
- Updated `LearningEntryFlow.build_missing_input_result()` to return a clarification-specific message when the fallback is low confidence rather than missing fields.
- Updated the router prompt to bias ambiguous educational requests toward `general_learning_clarification` with confidence below `0.6`.
- Added tests for low-confidence fallback in both the policy gate and the end-to-end learning-entry flow.

Files touched:

- `src/investory/agent_core/runtime/flow/investory_policy_gate.py`
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- `src/investory/agent_core/prompts/flows/learning_entry_router.md`
- `tests/test_investory_policy_gate.py`
- `tests/test_learning_entry_flow.py`
- `docs/2-2/worklog/routing-low-confidence-step4.md`

Verification:

- `pytest tests\test_investory_policy_gate.py` -> 14 passed, 1 existing pydantic warning.
- `.venv\Scripts\python.exe -m pytest tests\test_learning_entry_flow.py tests\test_learning_entry_router.py tests\test_investory_policy_gate.py tests\test_learning_entry_rules.py` -> 35 passed.
- `python -m py_compile src\investory\agent_core\runtime\flow\investory_policy_gate.py src\investory\agent_core\runtime\flow\learning_entry_flow.py tests\test_investory_policy_gate.py tests\test_learning_entry_flow.py` -> passed.

Result:

- Step 4 is implemented within the plan boundary. Optional LLM routing can no longer execute a task when route confidence is low; instead it falls back to a clarification response that keeps execution conservative.

## Step 5 - Add Per-Route Tests

Timestamp: 2026-06-01T01:09:45.0232966+10:00

Actions:

- Added explicit unknown-input fallback tests when routing is unresolved and no LLM router is configured.
- Added explicit high-confidence LLM route execution tests for `finance_qa`, `learning_material_summary`, and `instrument_brief`.
- Added endpoint-level coverage for unresolved payload fallback on `/learning-entry`.
- Kept low-confidence and clarification fallback tests from Step 4 in the same suite, so each route family now has a dedicated test path:
  - execute routes (`qa`, `summary`, `brief`)
  - refusal route
  - missing input route
  - low-confidence fallback route
  - unresolved/unknown fallback route

Files touched:

- `tests/test_investory_policy_gate.py`
- `tests/test_learning_entry_flow.py`
- `tests/test_learning_entry_gateway_api.py`
- `docs/2-2/worklog/routing-route-tests-step5.md`

Verification:

- `.venv\Scripts\python.exe -m pytest tests\test_learning_entry_flow.py tests\test_investory_policy_gate.py tests\test_learning_entry_gateway_api.py tests\test_learning_entry_router.py tests\test_learning_entry_rules.py` -> 47 passed.
- `python -m py_compile tests\test_learning_entry_flow.py tests\test_investory_policy_gate.py tests\test_learning_entry_gateway_api.py` -> passed.

Result:

- Step 5 is implemented within the plan boundary. Route behavior is now validated by dedicated tests across policy, flow, and gateway layers, including unknown/unresolved fallback and low-confidence fallback.
