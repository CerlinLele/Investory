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
