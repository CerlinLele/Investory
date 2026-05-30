# Investory Production 级 ReAct loop Implementation Steps

## 目标
把现有 `learning_entry` 升级为可收敛、可审计、可扩展的 ReAct runtime，且不破坏当前网关对外契约。

## Step 1: 定义统一的 ReAct 契约
### 要做什么
- 新建 ReAct 的状态、动作、审计模型，作为后续所有模块的唯一契约来源。

### 修改文件
- `src/investory/agent_core/contracts/react_loop.py`（新增）
- `src/investory/agent_core/contracts/learning_entry_state.py`
- `src/investory/agent_core/contracts/flow_state.py`

### 具体实现
1. 在 `react_loop.py` 定义 `str, Enum`：
   - `ReactLoopStatus`
   - `ReactAction`
2. 在 `react_loop.py` 定义 Pydantic 模型：
   - `ReactBudget`
   - `ReactStepRecord`
   - `ReactToolCallRecord`
   - `ReactAuditEvent`
   - `ReactLoopState`
3. 在 `learning_entry_state.py` 对齐运行态字段：
   - `status`, `step_count`, `max_steps`, `tool_call_count`, `max_tool_calls`, `audit_events`
4. 在 `flow_state.py` 增补兼容字段：
   - `step_count`, `max_steps`, `retry_count`, `requires_user_input`, `last_error`

### 完成标准
- 动作/状态不再出现裸字符串。
- 新旧 state 均可 `model_validate` 和 `model_dump`。
- 旧调用方无破坏性变更。

### 测试
- `pytest tests/test_flow_state.py`

## Step 2: 抽离 Policy Gate
### 要做什么
- 把“输入不足、越界请求、能力不足”这类逻辑集中成可复用纯函数。

### 修改文件
- `src/investory/agent_core/runtime/flow/react_policy_gate.py`（新增）
- `src/investory/agent_core/runtime/flow/learning_entry_rules.py`
- `src/investory/agent_core/runtime/flow/learning_entry_decision.py`

### 具体实现
1. 新增 `react_policy_gate.py`，实现：
   - `check_missing_fields(payload) -> PolicyDecision`
   - `check_investment_advice_boundary(payload) -> PolicyDecision | None`
   - `check_realtime_data_capability(payload) -> PolicyDecision | None`
   - `check_user_confirmation_requirement(payload) -> PolicyDecision | None`
2. 将 `learning_entry_rules.py` 中可复用判断保留为 helper，去掉流程控制职责。
3. `learning_entry_decision.py` 输出动作统一到 `ReactAction`（或显式映射到 `ReactAction`）。

### 完成标准
- Policy 检查函数无副作用、可单测。
- 决策输出只有一套动作语义。

### 测试
- `pytest tests/test_learning_entry_rules.py`
- 新增 `pytest tests/test_react_policy_gate.py`

## Step 3: 建立 Tool Registry
### 要做什么
- 禁止模型直接执行工具，所有工具调用必须经过注册和校验。

### 修改文件
- `src/investory/agent_core/runtime/flow/react_tool_registry.py`（新增）

### 具体实现
1. 定义 `ToolSpec`：
   - `name`
   - `input_model` 或 `args_schema`
   - `allowed_tasks`
   - `requires_confirmation`
2. 定义 `ToolRegistry`：
   - `register(spec)`
   - `get(name)`
   - `validate(tool_name, args, task_name)`
3. 校验失败返回统一结构化错误（可复用 `result_types.py` 的归一化模式）。

### 完成标准
- 未注册工具、越权工具、参数非法全部可被稳定拦截。

### 测试
- 新增 `pytest tests/test_react_tool_registry.py`

## Step 4: 实现 Bounded ReAct Runtime
### 要做什么
- 实现主循环，保证每轮有决策、可终止、可审计。

### 修改文件
- `src/investory/agent_core/runtime/flow/react_loop_runtime.py`（新增）

### 具体实现
1. 新建 `ReactLoopRuntime`，主流程固定为：
   - `plan_next_step`
   - `validate_action`
   - `execute_action_or_tool`
   - `record_observation`
   - `check_stop_condition`
2. 实现停止条件：
   - `action == finalize`
   - `action == ask_for_missing_input`
   - `action == refuse_and_redirect`
   - `step_count >= max_steps`
   - `tool_call_count >= max_tool_calls`
   - 重复动作超过阈值
3. 所有异常统一归一化并记录到 `audit_events`。

### 完成标准
- 无外部工具时可完整跑通追问/拒绝/执行/结束。
- 任意异常都可被结构化返回，不抛裸异常到网关层。

### 测试
- 新增 `pytest tests/test_react_loop_runtime.py`

## Step 5: 接入 Learning Entry Flow
### 要做什么
- 让 `learning_entry_flow` 变成 ReAct runtime 的包装层，保留现有 API。

### 修改文件
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`

### 具体实现
1. 将节点逻辑收敛为：
   - 初始化 `ReactLoopState`
   - 调用 `ReactLoopRuntime.run(...)`
   - 将 runtime 输出映射回 `TaskResult`
2. 保持 `run(payload, session_id)` 签名不变。
3. 兼容现有返回字段：`action`, `message`, `missing_fields`。

### 完成标准
- `/learning-entry` 入口行为对外兼容。
- 原有追问与拒绝路径不回归。

### 测试
- `pytest tests/test_learning_entry_flow.py`
- `pytest tests/test_learning_entry_gateway_api.py`

## Step 6: 打通执行上下文与审计链路
### 要做什么
- 让 task 执行流水线接收 loop 上下文，方便追踪每轮执行。

### 修改文件
- `src/investory/agent_core/runtime/task_execution_pipeline.py`
- `src/investory/agent_core/runtime/task_executor.py`
- `src/investory/agent_core/contracts/result_types.py`（如需扩展元数据）

### 具体实现
1. 在 `TaskExecutor.run(...)` 增加可选上下文参数（兼容旧签名）。
2. 在 pipeline 中透传 `trace_id`, `step_index`, `retry_count` 等信息。
3. 在 `TaskResult.result` 中保留最小执行元数据（仅可选字段，不破坏旧客户端）。

### 完成标准
- 旧调用方式继续可用。
- runtime 可从执行结果拿到轮次级元数据。

### 测试
- `pytest tests/test_task_executor.py`
- `pytest tests/test_task_execution_pipeline.py`

## Step 7: 网关响应协议兼容扩展
### 要做什么
- 扩展网关响应可选字段，承载决策与审计标识。

### 修改文件
- `src/investory/gateway/schemas.py`
- `src/investory/gateway/api.py`

### 具体实现
1. 在 `TaskResponse.result` 约定可选字段：
   - `decision`
   - `missing_fields`
   - `audit_id`
2. 保持字段可选，不新增必填项。
3. 确保未知任务、输入校验失败仍走原有 4xx 逻辑。

### 完成标准
- 旧客户端请求/解析不受影响。
- 新字段仅在相关流程返回。

### 测试
- `pytest tests/test_gateway_api.py`
- `pytest tests/test_learning_entry_gateway_api.py`

## Step 8: 全量回归与发布门槛
### 要做什么
- 对 ReAct runtime 相关路径做完整回归，确认可上线。

### 修改文件
- `tests/test_react_policy_gate.py`（新增）
- `tests/test_react_tool_registry.py`（新增）
- `tests/test_react_loop_runtime.py`（新增）
- `tests/test_learning_entry_flow.py`
- `tests/test_learning_entry_gateway_api.py`
- `tests/test_task_execution_pipeline.py`（按需）

### 具体实现
1. 覆盖关键路径：
   - 缺字段追问
   - 投资建议拒绝
   - 正常任务执行
   - `max_steps` 收敛
   - 重复动作终止
   - 工具调用拦截
   - 异常归一化
2. 执行回归测试：
   - `pytest tests/test_learning_entry_flow.py tests/test_learning_entry_gateway_api.py tests/test_task_execution_pipeline.py tests/test_request_runner.py`
3. 执行全量测试：
   - `pytest`

### 完成标准
- 所有新增测试通过。
- 无对外契约破坏。
- loop 强制边界（步数、工具数、策略拦截）全部生效。

## 推荐提交切分
1. `contracts + enums + state alignment`
2. `policy gate + tool registry`
3. `react loop runtime`
4. `learning entry integration`
5. `executor/pipeline metadata`
6. `gateway compatibility`
7. `tests and regression`

## Definition of Done
- ReAct runtime 在无工具与有工具场景都能收敛。
- 每轮有结构化审计事件。
- 所有动作与状态使用 `Enum` 或常量。
- `/learning-entry` 现有对外行为兼容。
- 全量测试通过。
