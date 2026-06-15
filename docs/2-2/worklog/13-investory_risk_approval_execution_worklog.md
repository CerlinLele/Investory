# 13 Investory Risk Approval Execution Worklog

## Phase 1

- Timestamp: `2026-06-11 23:41:36 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 1 - 补齐风险评估合约与固定常量`

### Actions

1. Added Phase 1 risk-assessment constants and enums in [investment_document_review.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\task_models\investment_document_review.py:29):
   - `INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME`
   - `COMPLIANCE_REVIEWER_ROLE`
   - `InvestmentDocumentReviewRiskLevel`
   - `InvestmentDocumentReviewApprovalStatus`
2. Added contract-only risk assessment models in [investment_document_review.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\task_models\investment_document_review.py:71):
   - `InvestmentDocumentReviewRiskAssessmentInput`
   - `InvestmentDocumentReviewRiskAssessmentResult`
3. Added focused validation coverage in [test_investment_document_review_task_model.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_task_model.py:47) for:
   - constant stability
   - risk assessment input validation
   - risk assessment result validation
4. Checked for an existing reusable result shell before expanding flow or API structure:
   - Search command: `rg -n "execution_trace|risk_assessment|approval" src\investory tests -g "*.py"`
   - Result: no existing `review.execution_trace` or risk/approval response shell was present in the current Python implementation.
   - Decision for Phase 1: keep `InvestmentDocumentReviewResult` unchanged and defer result-placement work to Phase 4, which matches the plan boundary.

### Files Touched

- [investment_document_review.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\task_models\investment_document_review.py:1)
- [test_investment_document_review_task_model.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_task_model.py:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_task_model.py`
  - Result: `6 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_tasks.py`
  - Result: `9 passed`

### Result

- Phase 1 completed.
- The repository now has typed, reusable risk-assessment enums and contract models without introducing raw business strings.
- No flow, prompt, TaskSpec, or API response shape changes were made in this phase.

## Phase 2

- Timestamp: `2026-06-11 23:47:04 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 2 - 新增独立 risk assessment task 与 prompt`

### Actions

1. Registered a dedicated risk-assessment `TaskSpec` in [tasks.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\tasks.py:102):
   - `INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK`
   - prompt name fixed to `investment_document_risk_assessment`
   - input/output models bound to the Phase 1 risk-assessment contracts
2. Added the task prompt in [investment_document_risk_assessment.md](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\prompts\tasks\investment_document_risk_assessment.md:1) with Phase 2 boundaries:
   - only use structured review evidence
   - do not request or rely on full document text
   - do not output investment advice
   - `high` risk must produce `critical_issues`
   - `low` / `medium` default to `auto_proceed=true`
   - `high` defaults to `auto_proceed=false`
3. Extended registry and routing checks:
   - [test_tasks.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_tasks.py:141) now asserts the new task is registered with the expected models.
   - [test_gateway_routing.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_gateway_routing.py:40) now asserts `resolve_task_spec("investment_document_risk_assessment")` resolves successfully.
4. Added prompt coverage in [test_investment_document_review_todo_prompts.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_todo_prompts.py:130) to verify the prompt preserves the no-full-document, no-advice, and `critical_issues` / `auto_proceed` constraints.

### Files Touched

- [tasks.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\tasks.py:1)
- [investment_document_risk_assessment.md](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\prompts\tasks\investment_document_risk_assessment.md:1)
- [test_tasks.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_tasks.py:1)
- [test_gateway_routing.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_gateway_routing.py:1)
- [test_investment_document_review_todo_prompts.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_todo_prompts.py:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_tasks.py`
  - Result: `10 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_gateway_routing.py`
  - Result: `7 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_todo_prompts.py`
  - Result: `5 passed`

### Result

- Phase 2 completed.
- `investment_document_risk_assessment` can now be resolved as a standalone task with its own prompt and structured IO contracts.
- Flow integration, payload building, and response-shape changes remain intentionally deferred to later phases.

## Phase 3

- Timestamp: `2026-06-12 20:45:42 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 3 - 在 flow 中插入 assess_review_risk 节点`

### Actions

1. Extended review flow state in [investment_document_review_state.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\contracts\investment_document_review_state.py:41):
   - `risk_assessment`
   - `approval_status`
   - `approval_required_role`
2. Inserted a dedicated risk-assessment hop into [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:570):
   - added `ASSESS_REVIEW_RISK` and `BUILD_PENDING_APPROVAL_RESULT` nodes
   - routed both `run_single_pass_review` and `execute_review_todo_plan` through `assess_review_risk`
   - added `route_after_risk_assessment` with `complete` and `pending_approval` branches
3. Added `_build_review_risk_assessment_payload()` and `_build_review_task_status_summary()` in [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:266) so the risk task consumes only:
   - synthesized single-pass findings
   - To-Do review summary aggregates
   - task completion status summaries
   - route confidence and document type
4. Added focused flow coverage in [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1633) for:
   - risk payload building from completed To-Do results
   - single-pass risk assessment payloads that do not forward raw `document_text`
   - pending-approval routing
5. Updated existing flow expectations in [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:338) so the tests now expect the additional `investment_document_risk_assessment` executor call after review generation.

### Files Touched

- [investment_document_review_state.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\contracts\investment_document_review_state.py:1)
- [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:1)
- [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py`
  - First result: `2 failed, 32 passed`
  - Failure cause:
    - `test_document_review_flow_executes_known_document_review_task` still expected the old single executor call and did not account for the new `investment_document_risk_assessment` hop.
    - `test_document_review_flow_uses_chunk_todo_path_for_multi_chunk_document` still expected the old tail call order and did not include the new post-synthesis risk assessment call.
  - Fix:
    - updated the two tests to expect the new risk-assessment executor call and adjusted the chunk-path tail sequence assertion
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py`
  - Final result: `34 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_rules.py`
  - Result: `23 passed`

### Result

- Phase 3 completed.
- Both the single-pass and To-Do review paths now pass through a shared `assess_review_risk` node before final result handling.
- The risk-assessment payload stays audit-friendly by consuming structured review outputs and task status summaries rather than re-reading raw document text.

## Phase 4

- Timestamp: `2026-06-12 20:56:12 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 4 - 把审查结果和审批状态分开输出`

### Actions

1. Expanded the outward result shape in [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:85) by adding stable response-field constants:
   - `RISK_ASSESSMENT_FIELD`
   - `APPROVAL_FIELD`
   - `STATUS_FIELD`
   - `REQUIRED_ROLE_FIELD`
2. Updated [build_final_result()](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:1394) so successful auto-approved results now return:
   - the existing user-readable `review`
   - a separate `risk_assessment`
   - a separate `approval` block
3. Implemented [build_pending_approval_result()](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:1423) so high-risk reviews are no longer exposed as plain `complete`:
   - `action` is now `pending_human_approval`
   - `review` remains present
   - `risk_assessment` remains present
   - `approval.status` and `approval.required_role` are explicit
4. Added Phase 4 flow assertions in [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1841):
   - final auto-approved results now include `risk_assessment` and `approval`
   - pending-approval results now expose `pending_human_approval` plus the minimal approval fields
5. Updated gateway coverage in [test_investment_document_review_gateway_api.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_gateway_api.py:118):
   - complete review responses now include `risk_assessment` and `approval`
   - the gateway executor stub now returns a valid risk-assessment payload
   - executor call order now includes the post-synthesis `investment_document_risk_assessment` step

### Files Touched

- [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:1)
- [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1)
- [test_investment_document_review_gateway_api.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_gateway_api.py:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py`
  - Result: `35 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_gateway_api.py`
  - Result: `7 passed`

### Result

- Phase 4 completed.
- User-readable review output remains intact while approval-oriented data is now exposed in separate `risk_assessment` and `approval` fields.
- High-risk results are no longer mislabeled as ordinary `complete`; they surface an explicit `pending_human_approval` action and approval status.

## Phase 5

- Timestamp: `2026-06-12 21:08:11 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 5 - 为后续人工审批 resume 留好扩展点`

### Actions

1. Added future approval-resume state fields in [investment_document_review_state.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\contracts\investment_document_review_state.py:42):
   - `approval_decision_at`
   - `approval_actor_role`
2. Clarified the resume boundary in [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:152) by documenting that the current resume store persists only To-Do review execution and that future approval-resume metadata remains on `InvestmentDocumentReviewState`.
3. Kept the existing `InvestmentDocumentReviewTodoResumeStore` protocol unchanged in this phase after evaluating the plan’s suggested additions:
   - no `approval_status` persistence added yet
   - no `approval_decision_at` persistence added yet
   - no `approval_actor_role` persistence added yet
   - decision: defer storage-contract expansion until a real approval resume entrypoint exists, so we do not prematurely lock in persistence semantics
4. Added tests to make the intended extension point explicit:
   - [test_investment_document_review_rules.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_rules.py:67) now checks the new approval resume fields default to `None` and validate cleanly when present.
   - [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1998) now verifies a pending-approval result can be rebuilt from already-completed review output plus approval metadata, without needing To-Do review resume inputs.

### Files Touched

- [investment_document_review_state.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\contracts\investment_document_review_state.py:1)
- [document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\src\investory\agent_core\runtime\flow\investment_document_review\document_review_flow.py:1)
- [test_investment_document_review_rules.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_rules.py:1)
- [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_rules.py`
  - Result: `24 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py`
  - Result: `36 passed`

### Result

- Phase 5 completed.
- The state model now has explicit fields for future approval decisions without changing current gateway output or To-Do resume storage contracts.
- The extension point is intentionally shaped so future approval resume can continue from a completed review and risk assessment instead of rerunning extract / analyze / synthesize.

## Phase 6

- Timestamp: `2026-06-12 21:21:03 +10:00`
- Plan: [13-Investory_参考v2加风险审批可借鉴点.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\plans\13-Investory_参考v2加风险审批可借鉴点.md)
- Scope: `Phase 6 - 补测试、兼容性与执行记录`

### Actions

1. Expanded end-to-end flow coverage in [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:402):
   - added a single-pass `medium` risk path that still returns `action=complete`
   - added a chunked To-Do `medium` risk path that still returns `action=complete`
   - added a `high` risk path that returns `action=pending_human_approval`
2. Expanded gateway compatibility coverage in [test_investment_document_review_gateway_api.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_gateway_api.py:205):
   - verified the HTTP response preserves `review`
   - verified `risk_assessment` is present for pending-approval responses
   - verified `approval.status` and `approval.required_role` are present and correct for high-risk reviews
3. Rechecked the earlier Phase 1 and Phase 2 contract/task coverage to keep Phase 6 evidence complete:
   - [test_investment_document_review_task_model.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_task_model.py:47)
   - [test_tasks.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_tasks.py:144)
   - [test_gateway_routing.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_gateway_routing.py:69)
   - [test_investment_document_review_todo_prompts.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_todo_prompts.py:131)

### Files Touched

- [test_investment_document_review_flow.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_flow.py:1)
- [test_investment_document_review_gateway_api.py](C:\Users\hy120\Downloads\AI project\Investory\tests\test_investment_document_review_gateway_api.py:1)
- [13-investory_risk_approval_execution_worklog.md](C:\Users\hy120\Downloads\AI project\Investory\docs\2-2\worklog\13-investory_risk_approval_execution_worklog.md:1)

### Verification

- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py`
  - First result: `39 passed`
  - Failure cause: none; the new Phase 6 flow coverage passed on the first run.
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_gateway_api.py`
  - First result: `8 passed`
  - Failure cause: none; the pending-approval gateway compatibility coverage passed on the first run.
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_task_model.py`
  - Result: `6 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_tasks.py`
  - Result: `10 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_gateway_routing.py`
  - Result: `7 passed`
- Command: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_todo_prompts.py`
  - Result: `5 passed`

### Result

- Phase 6 completed.
- The test suite now explicitly proves that `low` / `medium` reviews can auto-complete while `high` risk reviews stop at `pending_human_approval`.
- Final response compatibility is covered for both the internal flow result and the HTTP gateway response without widening business scope beyond tests and execution records.
