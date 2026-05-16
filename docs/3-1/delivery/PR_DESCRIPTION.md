# PR Title

Implement `web_search` tool chain with guarded HTTP execution and gateway task routing

## Summary

This PR implements a runnable `web_search` capability in Investory and wires it end-to-end through contract, tool, action executor/router, decision planner, and gateway task routing, while keeping `/tasks` API schema unchanged.

## What Changed

- Contract layer
  - Added `web_search` to `ToolName`
  - Documented recommended `ToolCall.params` keys: `query`, optional `top_k`, optional `provider_hint`
- Tool layer
  - Added `search_web(query, top_k=..., provider_hint=...) -> ToolResult`
  - Added provider fallback order (`provider_hint` first, then configured order)
  - Normalized result shape: `title/url/snippet/source/provider`
- Guard/config layer
  - Added web_search-specific config:
    - `web_search_timeout_seconds`
    - `web_search_allowed_hosts`
    - `web_search_max_results`
    - `web_search_provider_order`
  - Reused net guard allowlist/https checks and unified `tool_http_attempt` logging
- Action/runtime layer
  - Added action `run_web_search`
  - Added `RunWebSearchExecutor`
  - Registered route in `ActionRouter`
  - Added validator rules for `run_web_search` params
- Gateway/task layer
  - Added `web_search_brief` task model/spec
  - Added task aliases:
    - `web_search` -> `web_search_brief`
    - `research_lookup` -> `web_search_brief`
  - Decision planner routes `web_search_brief` directly to `run_web_search`
- Tests/docs
  - Added `tests/test_web_search_tool.py` (success/timeout/blocked_host/all providers fail)
  - Extended routing/planner/task-related tests for new task and action
  - Updated smoke default payload for `web_search_brief`
  - Updated locating doc and implementation worklog with code anchors

## Why

- Deliver a minimal but runnable web-search tool path compatible with current architecture.
- Keep current `/tasks` protocol stable while expanding available task types.
- Enforce network governance and observability from day one.

## Validation

- Passed:
  - `PYTHONPATH=src python -m pytest tests/test_web_search_tool.py tests/test_gateway_routing.py tests/test_tasks.py`
  - Result: `17 passed`
- Blocked in current environment:
  - `tests/test_action_executors.py`
  - `tests/test_action_router.py`
  - `tests/test_action_validator.py`
  - `tests/test_decision_planner.py`
  - Reason: `ModuleNotFoundError: No module named 'langchain_core'`

## Risks

- Runtime/provider risk: current provider adapters are example-based and need production provider integration.
- Environment/test risk: missing `langchain_core` blocks part of action-layer tests.
- Error-path UX risk: failed `run_web_search` currently maps to `requires_user_input` flow for consistency; may require future refinement.

## Rollback

- Revert commits in reverse order:
  - docs/test updates
  - gateway/task routing
  - action wiring
  - config/guard updates
  - tool/contract additions

## Reviewer Checklist

- Verify `web_search` contract + result schema consistency
- Verify provider fallback logic and governance config usage
- Verify gateway alias mapping and `/tasks` compatibility
- Verify action routing (`run_web_search`) and validator rules
- Verify known test blocker note is acceptable for merge policy
