# Investment Document Review V0 Route Migration Worklog (Retroactive)

Plan source: `docs/2-2/plans/08-Investory_投资文档审查助手v0路由迁移实施计划.md`

This worklog was reconstructed from git history after implementation. It records the v0 route migration work that introduced the investment document review contracts, rules, LLM router, single-pass review task, LangGraph flow, and gateway endpoint.

## Evidence Commands

Timestamp: 2026-06-06

Commands used:

- `git log --date=iso --format="%h%x09%ad%x09%s" 4cfcf63^..b43ff42 -- docs/2-2/plans/08-Investory_投资文档审查助手v0路由迁移实施计划.md src/investory/agent_core/contracts/investment_document_review_state.py src/investory/agent_core/runtime/flow/investment_document_review src/investory/agent_core/task_models/investment_document_review.py src/investory/agent_core/tasks.py src/investory/gateway src/investory/main.py tests/test_investment_document_review* tests/test_gateway_schemas.py tests/test_tasks.py`
- `rg -n "class InvestmentDocumentType|class InvestmentDocumentReviewRouteDecision|class InvestmentDocumentReviewState|DOCUMENT_TEXT_FIELD|class InvestmentDocumentReviewResult" src/investory/agent_core/contracts/investment_document_review_state.py src/investory/agent_core/task_models/investment_document_review.py`
- `rg -n "DOCUMENT_ROUTER_MAX_CHARS|def detect_missing_fields|def looks_like_investment_advice|def requires_realtime_data|def build_document_excerpt|DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE|def get_review_framework" src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py`
- `rg -n "class InvestmentDocumentReviewLLMRouter|def normalize_route_decision|INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS|InvestmentDocumentReviewNode|class InvestmentDocumentReviewFlow|INVESTMENT_DOCUMENT_REVIEW_ROUTE|InvestmentDocumentReviewRequest" src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py src/investory/agent_core/tasks.py src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py src/investory/gateway/api.py src/investory/gateway/schemas.py`

Result:

- The v0 migration plan was created on 2026-06-01 and refined during implementation.
- Implementation commits span 2026-06-01 14:53:49 +1000 through 2026-06-03 01:45:30 +1000.
- The current codebase contains the v0 contracts, rules, router, task model, task registration, flow orchestration, and gateway endpoint described by the plan.

## Planning Pass

Timestamp range: 2026-06-01 05:19:53 +1000 to 2026-06-03 00:49:52 +1000

Commits:

- `4cfcf63 docs: add investment document review migration plan`
- `f66f1e7 docs: detail document review v0 implementation steps`
- `6c1e7fb docs: remove review decision enum from investment doc plan`
- `23a9c11 docs: clarify document review missing-field semantics`
- `6b9ca68 docs: clarify input field semantics for document review`
- `1a98a3e docs(plan): add payload helper reuse plan for step 2`
- `f4fe58e docs(plan): explain why refusal is needed in policy gate`
- `e9c09c0 docs(plan): explain why missing branch is needed`
- `24e1a5c docs(document-review): clarify missing and refusal branches`

Actions:

- Added the initial v0 route migration plan.
- Broke the implementation into contracts/rules, router, single-pass review, flow orchestration, gateway wiring, and regression steps.
- Clarified the `document_text`, `document_type_hint`, and `review_goal` semantics.
- Clarified the distinction between missing-input branches and refusal branches.
- Added the shared payload-helper reuse direction for flow rules.

Files touched:

- `docs/2-2/plans/08-Investory_投资文档审查助手v0路由迁移实施计划.md`

Result:

- The plan became specific enough to execute in small commits.
- The migration boundary stayed focused on v0 routing and single-pass review; Todo/Plan/Reflection were explicitly left out.

## Step 1 - Establish Document Review Contracts

Timestamp: 2026-06-01 14:53:49 +1000

Commit:

- `531d1e2 feat(document-review): add investment review contracts`

Actions:

- Added document review field constants including `DOCUMENT_TEXT_FIELD`.
- Added `InvestmentDocumentType(str, Enum)` for known investment document types and `unknown`.
- Added `InvestmentDocumentReviewRouteDecision` with structured route output.
- Added `DocumentReviewFramework` and `InvestmentDocumentReviewState`.
- Added initial contract/state tests through `tests/test_investment_document_review_rules.py`.

Files touched:

- `src/investory/agent_core/contracts/investment_document_review_state.py`
- `tests/test_investment_document_review_rules.py`

Evidence:

- `src/investory/agent_core/contracts/investment_document_review_state.py:9` defines `DOCUMENT_TEXT_FIELD`.
- `src/investory/agent_core/contracts/investment_document_review_state.py:14` defines `InvestmentDocumentType`.
- `src/investory/agent_core/contracts/investment_document_review_state.py:23` defines `InvestmentDocumentReviewRouteDecision`.
- `src/investory/agent_core/contracts/investment_document_review_state.py:35` defines `InvestmentDocumentReviewState`.
- `tests/test_investment_document_review_rules.py:43` covers route-decision confidence validation.
- `tests/test_investment_document_review_rules.py:67` covers state defaults.

Result:

- Phase 1 contract foundations were implemented with typed constants/enums rather than scattered raw strings.

## Step 2 - Add Document Review Rules And Framework

Timestamp range: 2026-06-02 03:33:34 +1000 to 2026-06-02 03:45:04 +1000

Commits:

- `74a7981 feat(document-review): add review rules and framework`
- `de0a9fd refactor(flow-rules): extract shared payload helpers`

Actions:

- Added `DOCUMENT_ROUTER_MAX_CHARS = 600` to keep routing limited to the document excerpt.
- Added route confidence threshold and missing-field behavior.
- Added lightweight policy checks for missing document text, investment advice requests, and realtime-data requests.
- Added document excerpt construction.
- Added document-type-specific review frameworks for known types.
- Refactored shared payload helper logic into common flow helpers.

Files touched:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py`
- `src/investory/agent_core/runtime/flow/common/__init__.py`
- `src/investory/agent_core/runtime/flow/common/payload_rules.py`
- `src/investory/agent_core/runtime/flow/learning_entry/learning_entry_rules.py`
- `tests/test_investment_document_review_rules.py`

Evidence:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:17` defines `DOCUMENT_ROUTER_MAX_CHARS`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:58` defines `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:130` defines `detect_missing_fields`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:136` defines `looks_like_investment_advice`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:141` defines `requires_realtime_data`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:146` defines `build_document_excerpt`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py:151` defines `get_review_framework`.

Result:

- Phase 2 rules and framework selection were implemented.
- The implementation preserved the v0 boundary: route/classify first, do not review `unknown`, and do not turn user intent fields into investment advice handling.

## Step 3 - Implement The LLM Document Type Router

Timestamp range: 2026-06-02 18:12:16 +1000 to 2026-06-02 18:25:04 +1000

Commits:

- `d1e5c53 feat(document-review): add LLM document type router`
- `2e1488e refactor(runtime): reuse prompt message builder in routers`

Actions:

- Added the document review router prompt.
- Added `InvestmentDocumentReviewLLMRouter`.
- Routed only excerpt/hint/goal into the router prompt.
- Used `InvestmentDocumentReviewRouteDecision` as the structured output model.
- Added confidence normalization so low-confidence routes become `unknown`.
- Reused the shared prompt message builder in router code.

Files touched:

- `src/investory/agent_core/prompts/flows/investment_document_review_router.md`
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py`
- `src/investory/agent_core/runtime/message_builder.py`
- `tests/test_investment_document_review_router.py`

Evidence:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py:20` defines the router prompt file constant.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py:31` defines `normalize_route_decision`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py:49` defines `InvestmentDocumentReviewLLMRouter`.
- `tests/test_investment_document_review_router.py:38` verifies the route decision output model.
- `tests/test_investment_document_review_router.py:54` verifies the router uses the document excerpt rather than the full text.
- `tests/test_investment_document_review_router.py:75` verifies hint and review goal are included.

Result:

- Phase 3 LLM document-type routing was implemented and tested with fake runner coverage.

## Step 4 - Add Single-Pass Review Task Model

Timestamp: 2026-06-02 20:53:26 +1000

Commit:

- `e60db47 feat(document-review): add single-pass review task model`

Actions:

- Added the single-pass investment document review prompt.
- Added `InvestmentDocumentReviewInput`.
- Added `InvestmentDocumentReviewResult`.
- Added task model tests for payload validation, optional learning steps, and prompt message construction.

Files touched:

- `src/investory/agent_core/prompts/tasks/investment_document_review_single_pass.md`
- `src/investory/agent_core/task_models/investment_document_review.py`
- `tests/test_investment_document_review_task_model.py`

Evidence:

- `src/investory/agent_core/task_models/investment_document_review.py:27` defines `InvestmentDocumentReviewResult`.
- `tests/test_investment_document_review_task_model.py:11` covers the review input model.
- `tests/test_investment_document_review_task_model.py:26` covers the review result model.
- `tests/test_investment_document_review_task_model.py:41` covers prompt message construction.

Result:

- Phase 4 single-pass review model/prompt was implemented.
- The review output uses facts, risk findings, information gaps, boundary notes, summary, and learning next steps instead of a generic investment-suggestion field.

## Step 5 - Register Single-Pass Review Task Spec

Timestamp: 2026-06-03 00:27:26 +1000

Commit:

- `25df6a8 feat(document-review): register single-pass review task spec`

Actions:

- Added `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME`.
- Added `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK`.
- Registered the task spec in `TASKS`.
- Added tests for task spec lookup and model/prompt wiring.

Files touched:

- `src/investory/agent_core/tasks.py`
- `tests/test_tasks.py`

Evidence:

- `src/investory/agent_core/tasks.py:23` defines the single-pass task name constant.
- `src/investory/agent_core/tasks.py:49` defines `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK`.
- `src/investory/agent_core/tasks.py:60` registers the task in `TASKS`.
- `tests/test_tasks.py:44` verifies the single-pass task spec registration.

Result:

- Phase 5 task registration was implemented.
- The v0 flow can call the single-pass review through the project task execution abstraction.

## Step 6 - Implement Document Review Flow Orchestration

Timestamp: 2026-06-03 00:36:40 +1000

Commit:

- `9f97d08 feat(document-review): add document review flow orchestration`

Actions:

- Added `InvestmentDocumentReviewAction` result actions.
- Added `InvestmentDocumentReviewNode(str, Enum)` for graph nodes.
- Added `InvestmentDocumentReviewFlow`.
- Wired policy checks, document type classification, review framework construction, single-pass review execution, final result building, missing-input result, and refusal result.
- Added fake router/fake executor tests for missing input, refusal, unknown type, success path, and executor failure behavior.

Files touched:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
- `tests/test_investment_document_review_flow.py`

Evidence:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:66` defines `InvestmentDocumentReviewNode`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:76` defines `InvestmentDocumentReviewFlow`.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:112` starts graph node wiring.
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:253` calls `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK`.
- `tests/test_investment_document_review_flow.py:60` covers the missing-input branch.
- `tests/test_investment_document_review_flow.py:85` covers the investment-advice refusal branch.
- `tests/test_investment_document_review_flow.py:114` covers the realtime-data refusal branch.
- `tests/test_investment_document_review_flow.py:143` covers the unknown-document-type missing-input branch.
- `tests/test_investment_document_review_flow.py:180` covers the complete result branch.

Result:

- Phase 6 flow orchestration was implemented.
- The v0 graph keeps document review separate from learning-entry flow and avoids introducing Todo/Plan/Reflection.

## Step 7 - Expose Gateway Endpoint And Shared Schema

Timestamp range: 2026-06-03 01:16:52 +1000 to 2026-06-03 01:45:30 +1000

Commits:

- `9d9e223 feat(api): expose investment document review endpoint`
- `b43ff42 refactor(gateway): share flow request schema`

Actions:

- Added `/investment-document-review`.
- Added `InvestmentDocumentReviewRequest`.
- Added app-state flow injection for tests and runtime wiring.
- Added gateway tests for injected flow execution, endpoint missing-input branch, complete review execution, and flow failure conversion.
- Refactored gateway request schema to share a base flow request shape.

Files touched:

- `src/investory/gateway/api.py`
- `src/investory/gateway/schemas.py`
- `src/investory/main.py`
- `tests/test_gateway_schemas.py`
- `tests/test_investment_document_review_gateway_api.py`

Evidence:

- `src/investory/gateway/api.py:33` defines `INVESTMENT_DOCUMENT_REVIEW_ROUTE`.
- `src/investory/gateway/api.py:151` exposes the endpoint.
- `src/investory/gateway/schemas.py:54` defines `InvestmentDocumentReviewRequest`.
- `tests/test_gateway_schemas.py:44` validates the request schema.
- `tests/test_investment_document_review_gateway_api.py:63` verifies injected-flow execution.
- `tests/test_investment_document_review_gateway_api.py:85` verifies the endpoint missing-input branch.
- `tests/test_investment_document_review_gateway_api.py:106` verifies complete review execution through the endpoint.
- `tests/test_investment_document_review_gateway_api.py:137` verifies flow failure response conversion.

Result:

- Phase 7 API exposure was implemented.
- The public entry point is separate from `/learning-entry`, as required by the plan.

## Step 8 - Regression Scope

Evidence from tests added during implementation:

- `tests/test_investment_document_review_rules.py`
- `tests/test_investment_document_review_router.py`
- `tests/test_investment_document_review_task_model.py`
- `tests/test_investment_document_review_flow.py`
- `tests/test_investment_document_review_gateway_api.py`
- `tests/test_gateway_schemas.py`
- `tests/test_tasks.py`

Result:

- Git history shows focused tests were added alongside each implemented layer.
- This retroactive worklog does not claim a fresh full-suite run from the original implementation date.

## Current Status

Implemented:

- V0 document review contracts and typed document types.
- Lightweight missing/refusal/realtime rules.
- Document review framework selection.
- LLM document type router over an excerpt.
- Single-pass review task model and prompt.
- TaskSpec registration.
- LangGraph flow orchestration.
- Gateway endpoint and request schema.
- Focused tests across contracts, rules, router, task model, flow, gateway, and task registration.

Explicitly not implemented in v0, matching the plan boundary:

- TodoExecutionRunner-based task decomposition.
- Plan/Reflection stages.
- YAML framework loading.
- Agently/TriggerFlow dependency migration.
- Real file upload parsing.
- Realtime market data querying.
