# Investory 第08课全链路能力演进与投资理财场景映射

## 1. 结论

第 08 课的“智能文档审查助手”在 Investory 中有明确的对应场景。

Investory 不适合直接照搬“合同、政策、技术文档审查”的业务外壳，但非常适合演化成：

```text
投资材料学习审查助手
```

也就是面向 ETF、基金说明、券商材料、理财产品介绍、财报片段、金融课程材料等输入，完成事实抽取、风险识别、边界检查、学习报告生成，并避免越界输出个性化投资建议。

## 2. 第08课链路与 Investory 映射

| 第08课文档审查链路 | Investory 投资理财语境下的映射 |
|---|---|
| 输入文档 | ETF factsheet、基金说明书、产品介绍、财报片段、课程材料 |
| 路由识别 `doc_type` | 判断请求属于 `finance_qa`、`learning_material_summary`、`instrument_brief`、缺输入、拒答或澄清 |
| 动态生成审查任务 | 按材料、标的、风险维度、费用结构、适用学习场景拆分任务 |
| 按 `depends_on` 并发执行 | 多材料摘要、多标的 brief、多个风险维度抽取可并发执行 |
| 汇总风险并做 Plan 审批 | 投资建议、实时数据、用户确认、高风险动作由策略门前置拦截 |
| Reflection 优化报告 | 检查报告是否完整、是否伪造实时数据、是否越界成投资建议 |
| 服务化提供能力 | 通过 `/learning-entry` 或后续专门审查接口对外提供能力 |

## 3. 当前项目已有基础

Investory 当前已经具备全链路能力的雏形。

### 3.1 Routing / Policy Gate

现有入口链路已经不是简单的一次模型调用，而是先经过策略门和任务路由。

相关位置：

```text
src/investory/agent_core/runtime/flow/learning_entry_flow.py
src/investory/agent_core/runtime/flow/investory_policy_gate.py
src/investory/gateway/routing.py
```

当前已经支持的判断包括：

```text
missing input
investment advice request
realtime data not available
user confirmation required
low confidence route
ready to execute
```

这和第 08 课里的“先识别文档类型和风险路径，再交给后续模块处理”是同构的。

### 3.2 已有任务类型

当前项目已有三个核心任务：

```text
finance_qa
learning_material_summary
instrument_brief
```

它们正好可以对应投资材料审查中的三个输出形态：

| 任务 | 投资材料审查中的角色 |
|---|---|
| `finance_qa` | 回答材料内的学习型问题 |
| `learning_material_summary` | 对金融材料做学习摘要 |
| `instrument_brief` | 对 ETF、基金、股票、债券等标的生成学习简报 |

### 3.3 Todo + 并发基础

项目已经有 Todo 执行计划和并发 runner：

```text
src/investory/agent_core/contracts/todo_execution.py
src/investory/agent_core/runtime/todo_core/runner.py
```

已有能力包括：

```text
TodoTaskSpec
TodoExecutionPlan
depends_on
completion_criteria
DEFAULT_TODO_CONCURRENCY = 3
dependency layer execution
asyncio.gather
retry / fail_fast / best_effort
```

这说明项目已经具备第 08 课中“动态任务清单 + 依赖图 + 并发执行”的底层基础。

但当前主链路仍然主要是单任务执行：

```text
validate input
  -> build prompt
  -> call model
  -> validate output
  -> build result
```

也就是说，Todo runner 已存在，但还没有成为 `/learning-entry` 的默认复杂任务执行路径。

### 3.4 Reflection 仍是设计层

当前代码中还没有独立的 Reflection runner。

更适合的落地方式是把 Reflection 做成任务执行后的验收层，而不是混进单个 handler：

```text
Task Handler
  -> ReflectionEvaluator
  -> Optional Reviser
  -> Final Response
```

Reflection 应重点检查：

```text
是否覆盖输入材料核心信息
是否引入材料外事实
是否伪造实时行情
是否输出个性化投资建议
是否包含必要风险提示
是否结构清晰、适合学习用途
```

## 4. 最适合 Investory 的类似场景

### 4.1 多份 ETF 材料学习审查

示例输入：

```text
我上传了 VOO、QQQ、BND 三份 ETF 材料，帮我提取核心信息、费用、风险点、适用学习场景，并做横向对比。
```

可拆解为：

```text
t1: 生成 VOO instrument_brief
t2: 生成 QQQ instrument_brief
t3: 生成 BND instrument_brief
t4: 汇总三份 brief，比较资产暴露、费用、风险和学习重点，depends_on=[t1,t2,t3]
t5: Reflection 检查最终报告是否越界、是否完整，depends_on=[t4]
```

其中 `t1`、`t2`、`t3` 可以并发，`t4` 和 `t5` 需要等待前置任务完成。

### 4.2 基金或理财产品说明书审查

示例输入：

```text
帮我审查这份基金说明材料，提取费用、风险、投资范围、限制条件，并整理成学习报告。
```

注意这里的“审查”不是判断“值不值得买”，而是做学习型分析：

```text
事实抽取
费用结构解释
风险条款整理
限制条件说明
需要实时数据才能判断的部分标记
不能从材料直接推出的结论标记
```

### 4.3 财报或公告片段学习审查

示例输入：

```text
根据这段财报内容，帮我提取收入、利润、现金流、风险提示，并说明哪些结论不能仅凭这段材料得出。
```

这类场景适合加入 Reflection，因为模型容易把有限材料扩展成过度结论。

Reflection 应检查：

```text
是否区分事实与解释
是否避免材料外推断
是否避免价格预测
是否提示信息不足
```

## 5. 推荐目标链路

Investory 中的完整投资材料审查链路可以设计为：

```text
用户输入材料
  -> InvestoryPolicyGate
  -> LearningEntryRouter
  -> 识别任务类型或复杂审查意图
  -> 生成 TodoExecutionPlan
  -> 校验 depends_on 和 completion_criteria
  -> TodoExecutionRunner 并发执行可并行任务
  -> 汇总结构化结果
  -> Plan / Policy Gate 检查高风险动作和越界请求
  -> ReflectionEvaluator 检查最终报告质量和安全边界
  -> 返回学习型审查报告
```

## 6. 不建议做的方向

以下方向不适合当前 Investory：

```text
自动判断某个产品是否值得买
根据材料直接给买入、卖出、持有建议
自动生成个性化资产配置方案
绕过实时数据能力限制做行情判断
把 Reflection 当作投资合规的唯一防线
```

这些应该由前置 Policy Gate 或 Plan 层拦截，而不是先生成答案再靠 Reflection 修正。

## 7. 实现优先级建议

### 第一阶段：文档化和接口边界

先明确“投资材料学习审查”不是投资建议服务。

新增或保留以下设计边界：

```text
只基于用户提供材料
只做学习、摘要、风险点解释
不输出个性化买卖建议
需要实时数据的结论必须显式标记不可判断
```

### 第二阶段：接入 Todo 复杂任务路径

优先支持多材料或多标的任务：

```text
多份材料摘要
多个 instrument_brief 并发生成
多个 brief 的横向比较
```

这比拆分单个 `instrument_brief` 更有价值，因为任务之间天然独立，适合并发。

### 第三阶段：新增 Reflection 验收层

优先给以下任务加 Reflection：

```text
learning_material_summary
instrument_brief
多材料汇总报告
```

`finance_qa` 可以后置，因为它既包含学习型问题，也可能包含应由 Policy Gate 前置拦截的问题。

## 8. 总结

第 08 课的核心不是“文档审查”这个具体业务，而是：

```text
Routing + To-Do 并发 + Plan 风控 + Reflection 验收 + 服务化
```

Investory 的对应落点是：

```text
投资材料学习审查助手
```

当前项目已经具备 Routing、Policy Gate、TaskSpec、Todo runner 的基础。还缺的是把 Todo 复杂任务路径接入主流程，以及把 Reflection 做成独立的输出验收层。

因此，这个方向适合作为 Investory 从“单任务学习助手”升级到“投资材料审查与学习报告系统”的下一步。

## 9. learning_entry_flow 是否需要这么复杂

结论：通常不需要。

`learning_entry_flow` 更适合作为“学习入口分流层”，而不是“全链路编排层”。如果把 To-Do、Plan、Reflection、复杂文档审查全部堆进同一个入口 flow，会带来：

```text
普通请求路径变长（QA/summary/brief 也被拖慢）
状态字段膨胀（flow state 变成大而全）
测试矩阵急剧扩大（分支组合指数增长）
后续新增能力时改动面过大（回归风险上升）
```

更稳妥的边界是：

```text
learning_entry_flow
  -> 只负责前置策略 + 路由 + 单任务执行

investment_document_review_flow
  -> 负责文档类型识别、多任务审查、报告汇总、反思验收
```

推荐保留在 `learning_entry_flow` 的能力：

```text
InvestoryPolicyGate
规则路由（infer_candidate_task_type）
可选 LLM router（仅规则无法决策时）
低置信度兜底澄清
resolve_task_spec -> TaskExecutor
```

不建议默认塞进 `learning_entry_flow` 的能力：

```text
TodoExecutionRunner 主编排
PlanPolicyGate 审批编排
ReflectionRunner 多轮改写
文档审查专用 state / report 模型
```

一句话：`learning_entry_flow` 应该保持“轻入口”，复杂链路放到独立 flow，才能同时保证速度、可维护性和可扩展性。
