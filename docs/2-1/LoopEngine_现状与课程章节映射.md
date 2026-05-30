# Loop Engine 现状与课程章节映射（基于当前 Investory 实现）

## 1. 当前已实现（截至 Step 4）

### 1.1 通用 ReAct 契约（Step 1）
- 已有通用状态/动作枚举：`ReactLoopStatus`、`ReactActionType`。
- 已有通用运行模型：`ReactBudget`、`ReactStepRecord`、`ReactToolCallRecord`、`ReactAuditEvent`、`ReactLoopState`。
- `TaskFlowState` 已补通用运行字段：`step_count`、`max_steps`、`retry_count`、`requires_user_input`、`last_error`。

对应课程章节：
- 第 2 章（规划、决策、行动与结构化输出）：动作契约与结构化状态建模。

### 1.2 通用 Tool Registry（Step 2）
- 已实现 `ToolSpec`、`ToolRegistry.register/get/validate`。
- 已实现结构化校验错误返回（不抛业务文案异常）。
- 已覆盖工具未注册、任务越权、需确认、参数不合法、成功标准化返回等路径。

对应课程章节：
- 第 3 章（工具 / MCP 接入）：统一 tool contract、参数校验、权限与确认机制。

### 1.3 通用 Bounded Loop Engine（Step 3）
- 已实现固定主循环：`plan_next_step -> validate_step -> execute_step -> record_audit -> check_stop_condition`。
- 已实现停止条件：
  - `finalize`
  - `waiting_for_user`
  - `step_count >= max_steps`
  - `tool_call_count >= max_tool_calls`
  - 重复动作阈值
  - 非重试错误
- 已实现注入式接口：`StepPlanner`、`StepPolicy`、`StepExecutor`（无 Investory 业务耦合）。
- 已实现审计事件记录与基础失败重试门控。

对应课程章节：
- 第 2 章：结构化决策链路主干（Reason/Act 流程骨架）。
- 触达后续章节前置能力：
  - 第 10 章（可观测性）：audit/trace-like 事件记录。
  - 第 11 章（成本与可靠性）：预算、重试、收敛约束。

### 1.4 Investory Action 与 Policy（Step 4）
- 已新增业务动作枚举：`InvestoryAction`。
- 已新增 `InvestoryPolicyGate`，统一策略顺序：
  1) 缺字段  
  2) 投资建议越界识别  
  3) 实时数据能力检查  
  4) 用户确认需求  
  5) 可执行学习任务
- 已将 `learning_entry_rules.py` 收敛为纯 helper（规则判断下沉）。
- `learning_entry_flow.py` 已复用 helper，去除重复建议词判断实现。

对应课程章节：
- 第 2 章：结构化决策模式（业务策略层）。
- 第 5 章（Gateway 控制面）前置语义：输入约束与路由决策规则已具备基础。

## 2. 仍未实现（并标注属于后续章节）

### 2.1 引擎与业务适配集成（计划 Step 5/6）
- 未完成通用引擎与 Investory 任务执行的完整 adapter 闭环。
- 未完成 `LearningEntryFlow` 作为 orchestrator 完整接入 `LoopEngine` 的对外兼容改造（`/learning-entry` 全链路切换尚未落完）。

对应章节：
- 第 2 章（收尾）：planner/policy/executor 与业务执行链路打通。
- 第 6 章（Runtime 组装与运行时引擎）：跨层组装与统一运行时装配。
- 第 5 章（Gateway）：接口契约兼容与响应元数据透传。

### 2.2 工具/MCP 工程化细节（超出当前已做基础）
- 尚未形成完整 tool runtime（超时、熔断、统一回调/观测管线）。
- 尚未接入真实 MCP 运行链路与权限治理闭环。

对应章节：
- 第 3 章（工具 / MCP 接入）。
- 第 4 章（执行面与沙盒）：受限执行、安全边界、审批与回收。

### 2.3 可观测性与评测
- 目前 audit 事件为基础记录，尚未形成完整 `trace_id / step_id / replay` 体系。
- 尚未建立系统化 eval 样例集、回归基线与自动化评测链。

对应章节：
- 第 10 章（Eval、回归测试与可观测性）。

### 2.4 可靠性与服务化治理
- 尚未实现完整幂等策略（idempotency key 全链路治理）。
- 尚未实现系统级并发控制、排队策略、退避节奏、降级策略的服务化闭环。
- 尚未形成完善的成本治理与安全治理落地（预算策略、审批链、人机接管策略等）。

对应章节：
- 第 11 章（成本、可靠性、安全基线与服务化收束）。
- 第 4/5/6 章（执行面、Gateway、Runtime）中的并发与控制面协同部分。

## 3. 一句话结论

当前实现已经完成了课程第 2 章的核心“结构化决策+循环骨架”能力，并提前落了少量第 3/10/11 章的基础元素；但要达到课程后半段目标，仍需补齐 Step 5~8 以及第 6/10/11 章对应的运行时集成、观测评测与可靠性治理能力。
