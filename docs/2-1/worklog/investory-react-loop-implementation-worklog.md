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

## Step 3: 实现通用 Bounded Loop Engine（引擎层）

- Timestamp: `2026-05-31T05:02:07.2639054+10:00`
- Actions:
  - Added reusable bounded loop engine module under `runtime/react_core`.
  - Implemented injectable interfaces for `plan_next_step`, `validate_step`, and `execute_step` without domain coupling.
  - Implemented fixed loop orchestration sequence: `plan_next_step` -> `validate_step` -> `execute_step` -> `record_audit` -> `check_stop_condition`.
  - Implemented fixed stop conditions: finalize, waiting_for_user, max steps, max tool calls, repeated action limit, and non-retry error.
- Commands:
  - `pytest tests/test_react_loop_engine.py` -> `6 passed`.
- Files touched:
  - `src/investory/agent_core/runtime/react_core/loop_engine.py` (new)
  - `tests/test_react_loop_engine.py` (new)
- Result:
  - Step 3 implementation completed and test target passed.
- Evidence anchors:
  - `src/investory/agent_core/runtime/react_core/loop_engine.py:15`
  - `src/investory/agent_core/runtime/react_core/loop_engine.py:90`
  - `src/investory/agent_core/runtime/react_core/loop_engine.py:224`
  - `tests/test_react_loop_engine.py:57`
  - `tests/test_react_loop_engine.py:137`

## Step 4: 定义 Investory Action 与 Policy（业务层）

- Timestamp: `2026-05-31T05:25:14.7148728+10:00`
- Actions:
  - Added business action enum module `investory_actions.py` with typed action values.
  - Added `investory_policy_gate.py` to centralize policy checks:
    - missing field check
    - investment-advice boundary detection
    - realtime-data capability check
    - user-confirmation requirement check
  - Refactored `learning_entry_rules.py` into pure helpers by adding reusable rule functions and constants.
  - Updated `learning_entry_flow.py` to reuse `looks_like_investment_advice(...)` from helper rules instead of local duplicated advice-term logic.
- Commands:
  - `pytest tests/test_learning_entry_rules.py tests/test_investory_policy_gate.py` -> `15 passed`.
  - `pytest tests/test_learning_entry_flow.py` -> failed during collection (`ModuleNotFoundError: No module named 'langgraph'` in current environment).
- Files touched:
  - `src/investory/agent_core/runtime/flow/investory_actions.py` (new)
  - `src/investory/agent_core/runtime/flow/investory_policy_gate.py` (new)
  - `src/investory/agent_core/runtime/flow/learning_entry_rules.py`
  - `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
  - `tests/test_learning_entry_rules.py`
  - `tests/test_investory_policy_gate.py` (new)
- Result:
  - Step 4 implementation completed and required tests passed.
- Evidence anchors:
  - `src/investory/agent_core/runtime/flow/investory_actions.py:4`
  - `src/investory/agent_core/runtime/flow/investory_policy_gate.py:39`
  - `src/investory/agent_core/runtime/flow/learning_entry_rules.py:141`
  - `src/investory/agent_core/runtime/flow/learning_entry_flow.py:165`
  - `tests/test_investory_policy_gate.py:17`
  - `tests/test_learning_entry_rules.py:74`

### Step 4 更新逻辑说明

1. 先做动作类型收敛：
   - 新增 `InvestoryAction` 枚举，统一业务动作值，避免流程层散落裸字符串。
2. 将规则判断下沉为纯 helper：
   - 在 `learning_entry_rules.py` 增加投资建议识别、实时能力需求、确认需求、确认结果判断等规则函数与常量。
   - 规则层只做输入判断，不直接做流程路由。
3. 新增 `InvestoryPolicyGate` 作为业务决策入口：
   - 固定决策顺序为：缺字段 -> 越界建议 -> 实时能力 -> 用户确认 -> 可执行。
   - 返回结构化 `InvestoryPolicyResult`，不抛业务文案异常。
4. 移除流程层重复规则实现：
   - `learning_entry_flow.py` 删除本地建议词常量和 `_looks_like_investment_advice`，改为复用 `learning_entry_rules` helper。
5. 用测试锁定行为：
   - 新增 `test_investory_policy_gate.py` 覆盖 5 条策略主路径。
   - 扩展 `test_learning_entry_rules.py` 覆盖新增 helper 判定函数。
