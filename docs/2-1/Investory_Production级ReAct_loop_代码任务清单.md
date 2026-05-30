# Investory Production 级 ReAct loop Implementation Steps（复用版）

## 目标
按“通用引擎层 + Investory 业务层”实现 ReAct loop：
- 通用层可跨项目复用
- 业务层只放 Investory 规则与任务路由
- 不破坏当前 `/learning-entry` 对外契约

## 分层原则
- 通用引擎层：`src/investory/agent_core/runtime/react_core/`
- Investory 业务层：`src/investory/agent_core/runtime/flow/`
- 网关层：`src/investory/gateway/`

## Step 1: 定义通用 ReAct 契约（引擎层）
### 修改文件
- `src/investory/agent_core/contracts/react_loop.py`（新增）
- `src/investory/agent_core/contracts/flow_state.py`（最小兼容扩展）

### 实现动作
1. 在 `react_loop.py` 定义通用 `Enum`：
   - `ReactLoopStatus`
   - `ReactActionType`
2. 定义通用模型：
   - `ReactBudget`
   - `ReactStepRecord`
   - `ReactToolCallRecord`
   - `ReactAuditEvent`
   - `ReactLoopState`
3. 在 `flow_state.py` 仅补通用运行字段：
   - `step_count`, `max_steps`, `retry_count`, `requires_user_input`, `last_error`

### 完成标准
- 通用动作/状态不含 Investory 语义。
- 裸字符串状态与动作从核心运行态中移除。

### 测试
- `pytest tests/test_flow_state.py`

## Step 2: 建立通用 Tool Registry（引擎层）
### 修改文件
- `src/investory/agent_core/runtime/react_core/tool_registry.py`（新增）

### 实现动作
1. 定义 `ToolSpec`：
   - `name`
   - `args_model`
   - `requires_confirmation`
   - `allowed_task_names`
2. 定义 `ToolRegistry`：
   - `register(spec)`
   - `get(name)`
   - `validate(tool_name, args, task_name)`
3. 所有校验失败返回结构化错误对象，不抛业务文案。

### 完成标准
- 可复用到非 Investory 项目。
- 工具权限、参数合法性、确认需求均在注册表层完成。

### 测试
- `pytest tests/test_react_tool_registry.py`

## Step 3: 实现通用 Bounded Loop Engine（引擎层）
### 修改文件
- `src/investory/agent_core/runtime/react_core/loop_engine.py`（新增）

### 实现动作
1. 固定主循环：
   - `plan_next_step`
   - `validate_step`
   - `execute_step`
   - `record_audit`
   - `check_stop_condition`
2. 固定 stop 条件：
   - `finalize`
   - `waiting_for_user`
   - `step_count >= max_steps`
   - `tool_call_count >= max_tool_calls`
   - 重复动作阈值
   - 非重试错误
3. 通过接口注入策略与执行器，不硬编码 Investory 逻辑。

### 完成标准
- 引擎层不依赖 `learning_entry`、`finance_qa` 等业务对象。
- 任何领域仅通过注入 planner/policy/executor 接入。

### 测试
- `pytest tests/test_react_loop_engine.py`

## Step 4: 定义 Investory Action 与 Policy（业务层）
### 修改文件
- `src/investory/agent_core/runtime/flow/investory_actions.py`（新增）
- `src/investory/agent_core/runtime/flow/investory_policy_gate.py`（新增）
- `src/investory/agent_core/runtime/flow/learning_entry_rules.py`（收敛为 helper）

### 实现动作
1. 在 `investory_actions.py` 定义业务动作枚举：
   - `ask_for_missing_input`
   - `refuse_and_redirect`
   - `execute_learning_task`
   - `call_tool`
   - `finalize`
2. 在 `investory_policy_gate.py` 实现业务策略：
   - 缺字段检查
   - 投资建议越界识别
   - 实时数据能力检查
   - 用户确认需求判定
3. `learning_entry_rules.py` 只保留纯规则 helper。

### 完成标准
- 投资场景文案与策略只在业务层，不进入通用引擎层。

### 测试
- `pytest tests/test_learning_entry_rules.py`
- `pytest tests/test_investory_policy_gate.py`

## Step 5: 用适配器连接“通用引擎”与“Investory任务”
### 修改文件
- `src/investory/agent_core/runtime/flow/investory_loop_adapter.py`（新增）
- `src/investory/agent_core/runtime/task_executor.py`（最小接口扩展）
- `src/investory/agent_core/runtime/task_execution_pipeline.py`（透传上下文）

### 实现动作
1. `investory_loop_adapter.py` 实现：
   - 将业务动作映射到通用引擎动作
   - 将 `execute_learning_task` 路由到 `TaskExecutor`
   - 将工具调用路由到 `ToolRegistry`
2. `TaskExecutor.run(...)` 增加可选上下文字段，保持旧签名兼容。
3. pipeline 透传 `trace_id`, `step_index`, `retry_count`。

### 完成标准
- 业务逻辑不直连通用引擎内部细节。
- 未来换项目只需替换 adapter/policy。

### 测试
- `pytest tests/test_task_executor.py`
- `pytest tests/test_task_execution_pipeline.py`
- `pytest tests/test_investory_loop_adapter.py`

## Step 6: 接入 Learning Entry Graph（保持外部接口）
### 修改文件
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- `src/investory/agent_core/contracts/learning_entry_state.py`

### 实现动作
1. 将 `LearningEntryFlow` 变为 orchestrator：
   - 初始化 `LearningEntryState`
   - 调用 `InvestoryLoopAdapter + LoopEngine`
   - 回填 `TaskResult`
2. 保持 `run(payload, session_id)` 不变。
3. 保持返回字段兼容：`action`, `message`, `missing_fields`。

### 完成标准
- `/learning-entry` 客户端无感知升级。
- Graph 仍有 state，但 state 成为“业务入口态”而非“引擎实现细节”。

### 测试
- `pytest tests/test_learning_entry_flow.py`
- `pytest tests/test_learning_entry_gateway_api.py`

## Step 7: 网关协议最小扩展（可选元数据）
### 修改文件
- `src/investory/gateway/schemas.py`
- `src/investory/gateway/api.py`

### 实现动作
1. 给 `TaskResponse.result` 增加可选字段：
   - `decision`
   - `missing_fields`
   - `audit_id`
2. 保持全部可选，不新增必填字段。

### 完成标准
- 旧客户端兼容。
- 新调试字段仅在 loop 路径返回。

### 测试
- `pytest tests/test_gateway_api.py`
- `pytest tests/test_learning_entry_gateway_api.py`

## Step 8: 回归与复用验收
### 修改文件
- `tests/test_react_tool_registry.py`（新增）
- `tests/test_react_loop_engine.py`（新增）
- `tests/test_investory_policy_gate.py`（新增）
- `tests/test_investory_loop_adapter.py`（新增）
- `tests/test_learning_entry_flow.py`（更新）

### 实现动作
1. 覆盖核心路径：
   - 缺字段追问
   - 投资建议拒绝
   - 正常任务执行
   - max steps 收敛
   - 重复动作终止
   - 工具调用校验拦截
2. 额外增加“可复用验收”测试：
   - 构造一个假领域 policy/adapter，验证 loop engine 可运行。

### 完成标准
- 引擎层可脱离 Investory 独立运行。
- Investory 层不修改引擎即可完成业务策略迭代。
- 全量测试通过。

### 测试
- `pytest tests/test_react_loop_engine.py tests/test_investory_loop_adapter.py`
- `pytest`

## 提交建议（按复用边界切分）
1. `contracts: add reusable react loop state and enums`
2. `core: add reusable tool registry and loop engine`
3. `flow: add investory actions, policy gate, and adapter`
4. `flow: integrate learning entry graph with reusable loop engine`
5. `gateway: add optional loop metadata fields`
6. `test: cover core engine reuse and investory integration`

## Definition of Done
- 通用引擎层不包含 Investory 业务词汇与文案。
- Investory 业务层仅通过 policy/adapter 接入引擎。
- `/learning-entry` 对外契约兼容。
- loop 收敛约束与审计链路生效。
- 全量测试通过。
