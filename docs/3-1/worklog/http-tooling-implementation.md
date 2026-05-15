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
