# Investory 第 1-2 课适用场景（参考第04课案例）

## 课件案例可直接迁移的模式

基于“会议纪要 -> 待办 -> 跟进邮件”与“条件分支问答”的课件案例，适合迁移到 Investory 的有 4 个点：

1. 业务可读节点命名：节点名写业务动作，不写技术动作。
2. 两步线性先跑通：先用最短链路验证执行闭环。
3. 条件分支再加上：根据中间判断结果选择不同路径。
4. 工厂化封装：调用方只拿入口对象，不关心内部节点连接细节。

## Investory 推荐场景

投资学习问答分流（Orchestration only）

用户给出 `material_text` + `question` 后，系统先判断请求类型，再走不同处理路径，最终统一返回 `TaskResult`。

## 用户故事

用户问“我后天买某基金合适吗？”，系统不应直接给投资建议，而应：

- 判断是否属于投资建议请求
- 若是，拒答并给可学习的替代方向
- 若不是且字段完整，走任务模型输出学习型回答
- 若字段不完整，先追问缺失字段

## 场景流程设计

### 1) 两步线性基线（先落地）

```text
解析用户问题
-> 执行任务模型
-> 返回学习回答
```

这一步对应课件“两步线性流程”思想：先确保单链路稳定可跑。

### 2) 条件分支版本（目标形态）

```text
判定请求类型
-> [字段缺失] 引导补充信息
-> [投资建议请求] 拒答并给学习替代
-> [可执行学习问答] 执行任务模型
-> 统一返回结果
```

这一步对应课件“根据中间结果选路径”的条件分支模式。

## 运行时状态（对齐课件 data.value + runtime_data 思路）

建议本场景至少维护：

```python
state = {
    "task_id": "run-xxx",
    "task_name": "finance_qa",
    "input_payload": {...},
    "decision": None,           # 本次路由决策
    "action_call": None,        # 分支动作调用
    "action_result": None,      # 分支执行结果
    "output": None,             # 最终 TaskResult
    "error": None,
}
```

说明：

- `data.value` 等价语义：当前步骤直接输入输出。
- `runtime_data` 等价语义：跨分支仍要读取的共享中间信息（例如分类结果、缺失字段列表）。

## 与当前代码的映射

当前代码已基本具备这套分支编排骨架：

- `DecisionPlanner.decide(...)`：生成分支决策。
- `validate_decision_contract(...)`：做公共契约校验并构建 `action_call`。
- `route_by_action_key(...)`：根据 `action_call.action` 做条件分支路由。
- `ask_for_missing_input` / `answer_learning_question` / `refuse_advice_and_redirect`：执行三类动作节点。
- `ActionRouter.route(...)->executor.execute(...)`：按动作走不同执行器。
- `build_task_response(...)` + `backfill_action_result(...)`：把动作结果统一回 `TaskResult`。

对应文件：

- `src/investory/agent_core/runtime/decision_flow.py`
- `src/investory/agent_core/runtime/decision_planner.py`
- `src/investory/agent_core/actions/validator.py`

## 边界（本阶段不做）

本阶段边界（已对齐当前实现）：

- LangGraph 仅用于 `LearningQaOrchestrationFlow`（`DecisionFlow`）的编排层。
- `TaskExecutor` 仍是最小任务执行单位，不改职责。
- `TaskExecutionPipeline` 仍是 `TaskExecutor` 内部实现，不改为 LangGraph。

- 不引入并行分支汇聚（`.when` 同类能力）。
- 不引入持久化恢复、人工中断续跑。
- 不改 `RequestRunner`、模型配置与网关协议。

## 验收标准（仅编排层）

1. 节点名业务可读，且能映射到代码步骤。
2. 两步线性路径可稳定返回 `TaskResult(ok=True/False)`。
3. 条件分支三类路径行为可区分：缺失字段 / 拒答 / 执行模型。
4. 外部调用入口保持稳定：`TaskExecutor.run(...)` 或 `DecisionFlow.run(...)`。

## 工厂化建议（贴合课件 build_xxx_flow 思想）

可新增：

```python
build_investory_decision_flow(...) -> DecisionFlow
```

让 gateway 层只拿 flow 对象并调用 `run/start`，不关心内部节点结构。
