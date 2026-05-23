# Investory 多 Flow / 多 Planner 可扩展架构计划

## 目标

- 支持未来新增多个 `Flow` 与多个 `Planner`，避免入口层 `if/else` 膨胀。
- 稳定边界：`Flow` 只做编排，`Planner` 只做决策，`Executor` 只做执行副作用。
- 在不破坏现有 `LearningQaOrchestrationFlow` 行为的前提下逐步演进。

## 设计原则

1. 单一职责：
   - `Flow`: 图编排、节点路由、错误收束。
   - `Planner`: 决策推导（纯逻辑）。
   - `Action Executor`: 模型调用与副作用执行。
2. 面向接口：
   - 以 `Protocol` 或抽象基类约束 `Planner` 与 `Flow` 形状。
3. 可注册可扩展：
   - 新增任务类型通过注册表接入，不改入口主逻辑。
4. 向后兼容优先：
   - 迁移过程中保留旧导入入口，分阶段移除。

## 推荐模式组合

1. Strategy：
   - 各业务 `Planner` 实现统一接口。
2. Template Method：
   - `BaseOrchestrationFlow` 固化 `run()`、状态初始化、异常收束。
3. Command：
   - Action 执行节点通过独立 executor/handler 承担执行职责。
4. Registry + Factory：
   - 用注册表按 `task_type` 构建对应 `Flow` 与 `Planner`。

## 目录规划

```text
src/investory/agent_core/runtime/
  flow/
    base_orchestration_flow.py
    learning_qa_orchestration_flow.py
    ...
  planner/
    planner_protocol.py
    learning_qa_decision_planner.py
    ...
  registry/
    flow_registry.py
    planner_registry.py
    flow_factory.py
```

## 分阶段实施

### Phase 1：接口与基类落地

1. 新增 `PlannerProtocol`：
   - `decide(spec, payload) -> TaskDecision`
2. 新增 `BaseOrchestrationFlow`：
   - 统一 `run(spec, payload, request_id=None)` 生命周期。
   - 下沉通用异常收束逻辑。
3. 让 `LearningQaOrchestrationFlow` 继承基类（行为不变）。

交付物：

- 基类与协议代码。
- 现有 flow 迁移后测试全绿。

### Phase 2：注册表与工厂

1. 实现 `FlowRegistry` / `PlannerRegistry`。
2. 实现 `FlowFactory`：
   - 输入 `task_type`，输出已装配的 flow 实例。
3. Gateway 改为依赖工厂，不直接 `new LearningQaOrchestrationFlow(...)`。

交付物：

- 新注册入口。
- 至少 1 条端到端路径接入工厂并通过测试。

### Phase 3：多业务扩展验证

1. 新增第二个 planner（示例业务）。
2. 新增第二个 flow（可复用同一 `TaskExecutor`）。
3. 通过注册表接入，无需改 gateway 主体逻辑。

交付物：

- 第二业务的单测 + 集成测试。
- 注册表扩展示例。

### Phase 4：清理与收口

1. 移除过时兼容导入（确认无外部依赖后）。
2. 文档同步：
   - 架构图
   - 模块依赖关系
   - 新增 flow/planner 接入说明

交付物：

- 精简后的导入结构。
- 文档和代码一致。

## 测试策略

1. 单元测试：
   - 每个 planner 的决策规则。
   - 基类 flow 的异常收束行为。
2. 组合测试：
   - Flow + Planner + Router 的分支路径验证。
3. 回归测试：
   - 现有 `learning_qa` 全用例必须保持通过。

## 验收标准

1. 新增一个 planner 与 flow 不需要修改 gateway 主逻辑。
2. `Flow` 与 `Planner` 无循环依赖。
3. 错误收束策略统一，不因 flow 增加而复制代码。
4. 现有行为保持一致，回归测试全绿。

## 风险与应对

1. 风险：抽象过早导致复杂度上升。
   - 应对：每阶段只抽最小公共面，先让 `learning_qa` 跑通。
2. 风险：迁移期间导入路径断裂。
   - 应对：分阶段兼容 + 全量 `rg` 检查 + CI 回归。
3. 风险：注册表成为隐式耦合点。
   - 应对：强制类型检查与启动时注册校验。

## 下一步建议

1. 先执行 Phase 1，只做协议与基类，不引入新业务。
2. Phase 1 合并后再做 Phase 2（注册表与工厂）。
