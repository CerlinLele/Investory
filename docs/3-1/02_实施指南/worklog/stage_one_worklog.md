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

## Step 1.2: Extend ToolRegistry query methods

- Timestamp: `2026-06-21T17:06:00+10:00`
- Actions:
  - Added `ToolRegistry.list_all()` to return capability declarations for all registered tools.
  - Added `ToolRegistry.list_by_tag(tag)` to filter tools by business tag.
  - Added `ToolRegistry.list_by_side_effect(level)` to filter tools by side-effect level.
  - Added `ToolRegistry.get_spec_dict(name)` to expose one tool's capability declaration.
  - Added `ToolRegistry.get_func(name)` to return the stored executable function.
  - Added `ToolRegistry.call_func(name, args)` to invoke a registered tool function.
- Commands:
  - `Get-Content -LiteralPath 'src\investory\agent_core\runtime\react_core\tool_registry.py'`
  - `rg -n "def list_all|def list_by_tag|def list_by_side_effect|def get_spec_dict|def get_func|def call_func" 'src\investory\agent_core\runtime\react_core\tool_registry.py'`
- Files touched:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py`
- Result:
  - Step 1.2 completed successfully.
- Evidence anchors:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:66`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:70`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:78`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:86`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:91`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:96`

## Step 1.3: Verify the changes do not break existing tests

- Timestamp: `2026-06-21T17:09:00+10:00`
- Actions:
  - Ran the plan’s targeted pytest verification against the repo `.venv`.
  - Confirmed all selected existing tests passed, including the tool registry and task-related subset.
- Commands:
  - `.venv\Scripts\python.exe -m pytest tests/ -v -k "test_tool_registry or test_task" --tb=short`
- Files touched:
  - None
- Result:
  - `46 passed, 248 deselected`.
- Evidence anchors:
  - `pytest` output: `tests/test_react_tool_registry.py::test_tool_registry_register_and_get PASSED`
  - `pytest` output: `tests/test_tasks.py::test_tasks_registry_contains_initial_and_investment_document_review_tasks PASSED`

## Step 1.4: Add enhanced registry tests

- Timestamp: `2026-06-21T17:13:00+10:00`
- Actions:
  - Added `tests/test_tool_registry_enhanced.py` to cover listing, filtering, function lookup, and execution behavior.
  - Covered `list_all()`, `list_by_tag()`, `list_by_side_effect()`, `get_func()`, `call_func()`, and the missing-tool error path.
- Commands:
  - `Get-Content -LiteralPath 'tests\test_react_tool_registry.py'`
  - `.venv\Scripts\python.exe -m pytest tests\test_tool_registry_enhanced.py -v`
- Files touched:
  - `tests/test_tool_registry_enhanced.py`
- Result:
  - `6 passed in 0.05s`.
- Evidence anchors:
  - `tests/test_tool_registry_enhanced.py:1`
  - `tests/test_tool_registry_enhanced.py:15`
  - `tests/test_tool_registry_enhanced.py:38`
  - `tests/test_tool_registry_enhanced.py:61`
  - `tests/test_tool_registry_enhanced.py:82`
  - `tests/test_tool_registry_enhanced.py:101`
  - `tests/test_tool_registry_enhanced.py:116`
