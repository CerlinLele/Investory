# HTTP Tooling Implementation Worklog

## Step E-1 - 扩展 Tool Contract（新增 web_search）
- Timestamp: 2026-05-16 00:37:27 +10:00
- Command/Action:
  - Edited `src/investory/agent_core/contracts/tool_contract.py`.
  - Extended `ToolName` with `web_search`.
  - Added `ToolCall.params` description documenting `query`, `top_k`, `provider_hint` for `web_search`.
- Files touched:
  - `src/investory/agent_core/contracts/tool_contract.py`
- Result:
  - `ToolName` now supports both `fetch_instrument_profile` and `web_search`.
  - Existing `fetch_instrument_profile` contract remains unchanged and backward compatible.
- Evidence anchors:
  - `src/investory/agent_core/contracts/tool_contract.py:6`
  - `src/investory/agent_core/contracts/tool_contract.py:11`

## Step E-2 - 新增 web_search 工具实现
- Timestamp: 2026-05-16 01:16:17 +10:00
- Command/Action:
  - Added `src/investory/agent_core/tools/web_search.py` with `search_web(query, top_k=5, provider_hint=None) -> ToolResult`.
  - Implemented provider fallback order: `provider_hint` first (if supported), then default provider order.
  - Normalized success payload to `title/url/snippet/source/provider` result items.
  - Updated `src/investory/agent_core/tools/__init__.py` export list with `search_web`.
- Files touched:
  - `src/investory/agent_core/tools/web_search.py`
  - `src/investory/agent_core/tools/__init__.py`
- Result:
  - `web_search` now returns `ToolResult(ok=True)` with `data.results` structured list when at least one provider succeeds.
  - Provider failures converge to `ToolResult(ok=False)` with `error_type/retryable` policy.
- Evidence anchors:
  - `src/investory/agent_core/tools/web_search.py:125`
  - `src/investory/agent_core/tools/web_search.py:189`
  - `src/investory/agent_core/tools/__init__.py:1`

## Step E-3 - 接入 Guard 与网络治理
- Timestamp: 2026-05-16 01:32:39 +10:00
- Command/Action:
  - Added web_search config keys in `src/investory/config.py`: timeout, allowed_hosts, max_results, provider_order.
  - Wired `src/investory/agent_core/tools/web_search.py` to use web_search-specific config values.
  - Kept outbound validation via existing `guarded_get` allowlist checks and unified `tool_http_attempt` logging.
  - Added explicit parse-error attempt logging for observability consistency.
- Files touched:
  - `src/investory/config.py`
  - `src/investory/agent_core/tools/web_search.py`
- Result:
  - Non-allowlist targets are blocked by net guard using `web_search_allowed_hosts`.
  - Timeout/network/content-error paths produce stable `error_type/retryable` with observable log events.
- Evidence anchors:
  - `src/investory/config.py:75`
  - `src/investory/config.py:184`
  - `src/investory/agent_core/tools/web_search.py:25`
  - `src/investory/agent_core/tools/web_search.py:175`

## Step E-4 - 执行器与路由接线
- Timestamp: 2026-05-16 01:36:07 +10:00
- Command/Action:
  - Added new action name `run_web_search` to `ActionName` contract.
  - Added validator branch for `run_web_search` params: required `query`, optional positive `top_k`, optional non-empty `provider_hint`.
  - Added `RunWebSearchExecutor` and wired it to call `search_web`.
  - Registered `run_web_search` in default `ActionRouter` mapping.
- Files touched:
  - `src/investory/agent_core/contracts/action_contract.py`
  - `src/investory/agent_core/actions/validator.py`
  - `src/investory/agent_core/actions/executors.py`
  - `src/investory/agent_core/actions/router.py`
- Result:
  - `ActionRouter` can route `run_web_search` to `RunWebSearchExecutor`.
  - Executor output is returned as `ActionResult`, then backfilled to `TaskResult` by existing decision flow.
- Evidence anchors:
  - `src/investory/agent_core/contracts/action_contract.py:13`
  - `src/investory/agent_core/actions/validator.py:94`
  - `src/investory/agent_core/actions/executors.py:108`
  - `src/investory/agent_core/actions/router.py:45`
  - Compile check: `python -m compileall src/investory/agent_core/actions src/investory/agent_core/contracts` (passed).
