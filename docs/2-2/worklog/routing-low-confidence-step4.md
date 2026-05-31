# Routing Low Confidence Worklog

## Step 4 - Add Low Confidence Fallback

Timestamp: 2026-06-01T00:23:47.3795151+10:00

Plan source: the routing project-placement Markdown file under `docs/2-2`.

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
