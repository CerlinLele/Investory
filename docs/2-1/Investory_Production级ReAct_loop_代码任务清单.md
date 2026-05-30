# Investory Production 级 ReAct loop 代码任务清单（文件级）

## 适用范围
- 目标：把现有 `learning_entry` 从“单次路由 + 单次执行”升级为“有边界、可审计、可收敛”的 ReAct runtime。
- 原则：模型只做决策建议，程序负责策略约束、工具授权、停止条件与审计。

## Phase 1：契约与常量（先打地基）

### 1. 新增 `src/investory/agent_core/contracts/react_loop.py`
- 新增 `str, Enum`：
- `ReactLoopStatus`: `running`, `waiting_for_user`, `completed`, `refused`, `failed`, `max_steps_exceeded`
- `ReactAction`: `ask_for_missing_input`, `refuse_and_redirect`, `execute_learning_task`, `call_tool`, `finalize`
- 新增模型：
- `ReactBudget`
- `ReactStepRecord`
- `ReactToolCallRecord`
- `ReactAuditEvent`
- `ReactLoopState`
- 验收标准：
- 所有动作、状态、事件类型不再使用裸字符串。
- `ReactLoopState` 可独立被 `model_validate` 与 `model_dump`。

### 2. 修改 `src/investory/agent_core/contracts/learning_entry_state.py`
- 将可复用字段对齐到 `ReactLoopState`：
- 保留 `session_id`, `input_payload`, `candidate_task_type`, `output`, `error`
- 新增或映射：`status`, `step_count`, `max_steps`, `tool_call_count`, `max_tool_calls`, `audit_events`
- 验收标准：
- 学习入口状态可承载多轮 loop 运行信息，不丢失原有字段语义。

### 3. 修改 `src/investory/agent_core/contracts/flow_state.py`
- 保持兼容前提下，补充通用运行字段（若该状态继续使用）：
- `step_count`, `max_steps`, `retry_count`, `requires_user_input`, `last_error`
- 验收标准：
- 老调用方不报错；新增字段有默认值。

## Phase 2：ReAct runtime（核心运行时）

### 4. 新增 `src/investory/agent_core/runtime/flow/react_policy_gate.py`
- 提供纯函数策略检查：
- `check_missing_fields`
- `check_investment_advice_boundary`
- `check_realtime_data_capability`
- `check_user_confirmation_requirement`
- 输出统一决策对象（含 `action`, `reason`, `missing_fields`）。
- 验收标准：
- 策略函数无副作用，可单测覆盖每个分支。

### 5. 新增 `src/investory/agent_core/runtime/flow/react_tool_registry.py`
- 定义工具注册与校验接口：
- `ToolSpec`（名称、参数 schema、是否需确认、允许任务）
- `ToolRegistry`（register/get/validate）
- 验收标准：
- 未注册工具、越权工具、参数非法均返回结构化错误。

### 6. 新增 `src/investory/agent_core/runtime/flow/react_loop_runtime.py`
- 实现 bounded loop 主循环：
- `plan_next_step`
- `validate_action`
- `execute_action_or_tool`
- `record_observation`
- `check_stop_condition`
- 支持停止条件：
- `finalize`
- `ask_for_missing_input`
- `refuse_and_redirect`
- `max_steps` 触发
- `max_tool_calls` 触发
- 重复动作阈值触发
- 验收标准：
- 无外部工具时也能闭环（追问、拒绝、执行 task、完成）。
- 任意异常都会转成结构化错误并写入审计事件。

## Phase 3：接入现有入口流

### 7. 修改 `src/investory/agent_core/runtime/flow/learning_entry_flow.py`
- 将当前节点职责收敛为“初始化状态 + 调用 ReactLoopRuntime + 回填 TaskResult”。
- 保留现有 API 契约：`run(payload, session_id)`。
- 验收标准：
- `/learning-entry` 行为对外兼容。
- 追问与拒绝动作仍可返回当前协议字段。

### 8. 修改 `src/investory/agent_core/runtime/flow/learning_entry_rules.py`
- 将“字段探测与候选任务推断”改为 runtime 可复用 helper。
- 对外保持纯函数；移除重复分支判断。
- 验收标准：
- 规则函数只做规则，不做流程控制。

### 9. 修改 `src/investory/agent_core/runtime/flow/learning_entry_decision.py`
- 对齐 `ReactAction` 或新增映射层，避免双份动作枚举漂移。
- 验收标准：
- policy 决策只输出一套动作语义。

## Phase 4：执行层与网关对齐

### 10. 修改 `src/investory/agent_core/runtime/task_execution_pipeline.py`
- 增加可选上下文参数（如 `trace_id`、`step_index`）以便 runtime 审计。
- 在 `build_task_result` 写入最小执行元数据（不破坏现有 `TaskResult` 结构）。
- 验收标准：
- 现有 task 测试不回归；新增元数据可被审计层消费。

### 11. 修改 `src/investory/agent_core/runtime/task_executor.py`
- 允许 runtime 传入执行上下文并透传到 pipeline。
- 验收标准：
- 旧调用方式 `run(spec, payload)` 保持可用。

### 12. 修改 `src/investory/gateway/schemas.py`
- 给 `TaskResponse.result` 增补可选调试字段协议（例如 `decision`, `missing_fields`, `audit_id`）。
- 字段保持可选，避免破坏客户端。
- 验收标准：
- 网关 schema 兼容旧请求/响应。

### 13. 修改 `src/investory/gateway/api.py`
- `run_learning_entry` 接入新的 runtime 输出字段。
- 保持错误转换逻辑稳定。
- 验收标准：
- API 层不出现 500；未知任务和校验失败仍返回既定 4xx 响应。

## Phase 5：测试与回归（必须同步）

### 14. 新增 `tests/test_react_loop_runtime.py`
- 覆盖：
- 缺字段追问分支
- 投资建议拒绝分支
- 正常执行分支
- `max_steps` 收敛分支
- 重复动作终止分支
- 异常归一化分支
- 验收标准：
- 每个停止条件至少 1 个正向用例。

### 15. 新增 `tests/test_react_policy_gate.py`
- 覆盖规则函数矩阵（输入样式、边界词、空值、混合语言）。
- 验收标准：
- 规则命中稳定，不依赖模型输出。

### 16. 修改 `tests/test_learning_entry_flow.py`
- 对齐新 runtime 接入后的行为断言。
- 验收标准：
- 既有入口流场景全部通过，新增审计字段断言通过。

### 17. 修改 `tests/test_learning_entry_gateway_api.py`
- 覆盖 `/learning-entry` 响应兼容性与新增可选字段。
- 验收标准：
- 客户端最小契约保持稳定。

### 18. 选择性修改 `tests/test_task_execution_pipeline.py`
- 若执行元数据扩展触发行为变化，补充对应断言。
- 验收标准：
- pipeline 成功/失败路径均保持可预测输出。

## 交付门槛（Definition of Done）
- ReAct loop 在无工具场景下可稳定完成“追问/拒绝/执行/结束”四类流程。
- 每轮都有结构化审计事件，包含动作、原因、结果、错误（若有）。
- `max_steps` 与 `max_tool_calls` 在代码层强制生效。
- 所有新增/修改测试通过，且网关公共契约不破坏。
- 关键动作、状态、路由值全部使用 `Enum` 或模块常量，不残留裸字符串。

## 建议执行顺序（最小可用增量）
1. 完成 Phase 1 + Phase 2（先做 runtime 可单测运行）。
2. 完成 Phase 3（接入 learning entry）。
3. 完成 Phase 4（打通网关与执行上下文）。
4. 完成 Phase 5（补齐回归与稳定性验证）。
