# Investory Production ReAct Loop Worklog

## Step 1: 定义通用 ReAct 契约（引擎层）

- Timestamp: `2026-05-31T04:24:06.2324586+10:00`
- Actions:
  - Added reusable ReAct contract module with typed enums and loop state models.
  - Extended `TaskFlowState` with generic runtime fields required by loop orchestration.
  - Exported new reusable contracts via `contracts.__init__`.
  - Extended `test_flow_state` default assertions for newly added compatibility fields.
- Commands:
  - `pytest tests/test_flow_state.py` -> `7 passed, 1 warning`.
- Files touched:
  - `src/investory/agent_core/contracts/react_loop.py` (new)
  - `src/investory/agent_core/contracts/flow_state.py`
  - `src/investory/agent_core/contracts/__init__.py`
  - `tests/test_flow_state.py`
- Result:
  - Step 1 implementation completed and test target passed.
- Evidence anchors:
  - `src/investory/agent_core/contracts/react_loop.py:8`
  - `src/investory/agent_core/contracts/react_loop.py:17`
  - `src/investory/agent_core/contracts/react_loop.py:62`
  - `src/investory/agent_core/contracts/flow_state.py:21`
  - `src/investory/agent_core/contracts/__init__.py:7`
  - `tests/test_flow_state.py:32`

## Step 2: 建立通用 Tool Registry（引擎层）

- Timestamp: `2026-05-31T04:46:24.5511098+10:00`
- Actions:
  - Added reusable tool registry contracts and validation flow under `runtime/react_core`.
  - Implemented `ToolSpec` with `name`, `args_model`, `requires_confirmation`, and `allowed_task_names`.
  - Implemented `ToolRegistry.register(spec)`, `ToolRegistry.get(name)`, and `ToolRegistry.validate(tool_name, args, task_name)`.
  - Added structured validation result and typed error codes so validation failures return objects instead of business-message exceptions.
- Commands:
  - `pytest tests/test_react_tool_registry.py` -> `6 passed`.
- Files touched:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py` (new)
  - `tests/test_react_tool_registry.py` (new)
- Result:
  - Step 2 implementation completed and test target passed.
- Evidence anchors:
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:10`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:32`
  - `src/investory/agent_core/runtime/react_core/tool_registry.py:49`
  - `tests/test_react_tool_registry.py:25`
  - `tests/test_react_tool_registry.py:79`

### validate(tool_name, args, task_name) 逻辑说明

按“先拦截、再校验、最后标准化返回”的顺序执行：

1. 工具是否已注册：
   - 通过 `get(tool_name)` 查找。
   - 未注册则返回 `ok=False`，错误码 `tool_not_registered`。
2. 任务权限是否允许：
   - 当 `allowed_task_names` 非空且不包含 `task_name` 时拒绝。
   - 返回 `ok=False`，错误码 `tool_not_allowed_for_task`。
3. 是否满足确认要求：
   - 当 `requires_confirmation=True` 且 `args.confirmation_granted` 不为真时拒绝。
   - 返回 `ok=False`，错误码 `confirmation_required`。
4. 参数结构校验：
   - 移除内部确认字段 `confirmation_granted` 后，使用 `args_model.model_validate(...)` 校验。
   - 校验失败返回 `ok=False`，错误码 `invalid_tool_args`，并在 `details.errors` 中携带 Pydantic 错误详情。
5. 成功返回标准化结果：
   - 返回 `ok=True`。
   - `normalized_args` 使用 `model_dump()` 输出标准化参数。
   - 同步回传 `requires_confirmation` 标记。

设计约束：
- 不抛业务文案异常，所有失败统一走结构化错误对象返回，便于引擎层复用与上层统一处理。
