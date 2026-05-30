# Investory Production 级 ReAct loop 定制方案

## 结论
Investory 应采用“模型负责推理、程序负责约束和执行”的定制 ReAct loop，而不是直接依赖默认 loop。

推荐主链路：

```text
Policy Gateway
-> Planner
-> Bounded ReAct Runtime
-> Tool Executor
-> Verifier
-> Finalizer
```

## 当前代码基础与定制位置
- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`：已有入口编排（LangGraph）。
- `src/investory/agent_core/runtime/task_execution_pipeline.py`：单次 task 执行流水线。
- `src/investory/agent_core/runtime/request_runner.py`：模型调用与重试。

定制重点应放在 `runtime/flow`（或新增 `runtime/react`）层，不建议塞进 `RequestRunner`。

## 核心定制点

### 1) 增加生产级 loop 状态契约
当前 `flow_state.py` 字段偏薄，建议新增：
- `step_count`
- `max_steps`
- `tool_call_count`
- `max_tool_calls`
- `retry_count`
- `budget`
- `audit_events`
- `requires_user_input`
- `last_error`

建议增加状态枚举：
- `running`
- `waiting_for_user`
- `completed`
- `refused`
- `failed`
- `max_steps_exceeded`

### 2) 用 Enum 固化动作（避免模型自由发明）
建议动作枚举：
- `ask_for_missing_input`
- `refuse_and_redirect`
- `answer_finance_question`
- `summarize_learning_material`
- `generate_instrument_brief`
- `call_tool`
- `finalize`

### 3) 引入 Policy Gate（程序决定是否允许执行）
每轮先做规则拦截：
- 是否越界到投资建议
- 是否请求个性化资产配置
- 是否需要实时数据但当前无工具
- 是否缺关键字段
- 是否需要用户确认

### 4) 实现 bounded loop（必须可收敛）
每轮固定步骤：

```text
plan_next_step
-> validate_action
-> execute_action_or_tool
-> record_observation
-> check_stop_condition
```

停止条件至少包括：
- `action == finalize`
- `action == ask_for_missing_input`
- `action == refuse_and_redirect`
- `step_count >= max_steps`
- `tool_call_count >= max_tool_calls`
- 重复动作达到阈值
- 非重试错误

### 5) 工具调用统一走 Tool Registry
模型只输出结构化调用意图，不直接执行函数。

程序侧校验：
- 工具是否注册
- 参数是否通过 schema 校验
- 当前任务是否允许该工具
- 是否超预算
- 是否需要人工确认

### 6) 增加审计与可观测性
建议记录：
- `task_id`
- `session_id`
- `step_index`
- `decision/action`
- `tool_name`
- `sanitized_args`
- `result_summary`
- `error_type`
- `latency_ms`
- `retry_count`
- `policy_decision`

## 分阶段落地建议
1. 先扩展 contracts：`ReactLoopState`、`ReactAction`、`ToolCallRecord`、`AuditEvent`。
2. 新建 `ReactLoopRuntime`，先支持 `ask/refuse/execute_task/finalize`。
3. 将现有 `LearningEntryFlow` 的缺字段检查、拒绝策略、任务路由迁移到 runtime 节点。
4. 增加强约束：`max_steps`、`max_tool_calls`、`max_retries`、`timeout`。
5. 再接入外部工具（如基金资料查询），保持同一动作与审计协议。
6. 最后扩展并行工具、缓存与回放能力。

## 第一版目标（建议）
第一版不要追求“通用 Agent 平台”，先聚焦 Investory 的高风险点：
- 输入不足时稳定追问
- 投资建议请求稳定收束
- 无实时数据时不幻觉回答
- 每一步可追踪、可审计、可终止

