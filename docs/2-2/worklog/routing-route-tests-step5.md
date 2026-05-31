# Routing Route Tests Worklog

## Step 5 - Add Per-Route Tests

Timestamp: 2026-06-01T01:09:45.0232966+10:00

Plan source: the routing project-placement Markdown file under `docs/2-2`.

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
