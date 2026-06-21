# Stage One Worklog

## Step 1.1: Extend ToolSpec data class

- Timestamp: `2026-06-21T16:59:02.2653351+10:00`
- Actions:
  - Extended `ToolSpec` with backward-compatible fields for executable function, description, side-effect level, and tag.
  - Added `ToolSpec.to_spec_dict()` so the registry can later expose capability metadata without the executable function.
  - Preserved existing `requires_confirmation` and `allowed_task_names` behavior.
- Commands:
  - `Get-Content -LiteralPath 'src\investory\agent_core\runtime\react_core\tool_registry.py'`
  - `rg -n "class ToolSpec|func: Callable|desc: str|side_effect_level: str|tag: str|def to_spec_dict" 'src\investory\agent_core\runtime\react_core\tool_registry.py'`
- Files touched:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py`
- Result:
  - Step 1.1 completed successfully.
- Evidence anchors:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:35`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:38`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:45`
