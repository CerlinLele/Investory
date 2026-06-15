# Investory 第2-2课：Reflection 内容提取与项目适用性

## 1. Reflection 模式核心内容

Reflection 是一种“执行后验收”的结构化决策模式，目标不是让模型无限自我思考，而是用明确标准对结果做质量检查，并在有限轮次内改进。

典型流程：

```text
Generate -> Evaluate -> Revise -> Evaluate -> ... -> Pass / Max Rounds
```

对应到示例 `s04_reflection.py`：

| 阶段 | 职责 | 关键输入 | 关键输出 |
|---|---|---|---|
| `generate_draft` | 生成初稿 | `task` | `draft` |
| `evaluate` | 对照标准评估当前版本 | `task`, `draft`, `criteria` | `passed`, `score`, `issues`, `suggestions` |
| `revise` | 根据评估建议改写 | `task`, `draft`, `suggestions` | `new_draft` |
| 终止条件 | 防止死循环 | `max_rounds`, `passed` | `final_result`, `total_rounds` |

关键设计点：

- `criteria` 必须明确，否则评估会变成主观打分。
- `issues` 面向人类解释问题，`suggestions` 面向模型执行修改。
- `max_rounds` 是安全阀，必须存在。
- Reflection 循环的是“内容质量改进”，不是工具调用。
- 它和 ReAct Loop 同构，但关注点不同：ReAct 是 `Reason -> Act -> Observe`，Reflection 是 `Evaluate -> Revise -> Evaluate`。

## 2. 与第07课结构化决策体系的关系

第07课把结构化决策拆成四类：

| 模式 | 决策时机 | 解决问题 | Investory 当前相关性 |
|---|---|---|---|
| Routing | 输入进入时 | 交给哪个任务处理 | 已有 `LearningEntryRouter` 和 `InvestoryPolicyGate` |
| To-Do + 并发 | 执行开始前 | 如何拆解、哪些可并发 | 可用于多材料摘要、多标的对比 |
| Plan | 高风险执行前 | 是否需要审批 | 可用于用户确认、实时数据、投资建议边界 |
| Reflection | 执行完成后 | 结果是否达标 | 适合加在生成型任务的输出后 |

Investory 目前已经具备 Routing 和 Policy Gate 的雏形：

- `LearningEntryRoute` 定义了 `finance_qa`、`learning_material_summary`、`instrument_brief` 等任务路由。
- `LearningEntryRouteDecision` 已经使用结构化字段：`route`、`confidence`、`reason`、`missing_fields`。
- `InvestoryPolicyGate` 已经有低置信度兜底、缺字段检测、投资建议拒答、实时数据能力检查、用户确认检查。

因此 Reflection 不应该替代当前入口路由和策略门，而应该作为“任务执行后的验收层”接在具体任务 handler 之后。

## 3. Investory 中最适合 Reflection 的场景

### 3.1 学习材料摘要

适用性：高。

原因：

- 摘要是典型生成型任务，质量容易出现遗漏、过长、结构不清。
- 可以定义稳定 criteria，例如覆盖主题、保留关键概念、区分事实与解释、避免投资建议。
- 修改成本低，失败后重新改写不会产生外部副作用。

建议评估标准：

- 是否覆盖输入材料的核心主题。
- 是否保留关键术语、定义、步骤或结论。
- 是否没有引入材料外的事实断言。
- 是否没有输出个性化投资建议。
- 是否符合长度、结构、语言风格要求。

推荐配置：

```text
max_rounds = 2
pass_score_threshold = 0.85
```

### 3.2 标的简介 / Instrument Brief

适用性：高，但需要更强事实约束。

原因：

- 标的简介需要结构完整：基本信息、业务/资产属性、风险点、学习用途说明。
- 这类输出容易混入“买入/卖出/推荐”等越界表达。
- Reflection 可以检查是否缺少风险提示、是否使用了不支持的实时数据、是否越界为投资建议。

建议评估标准：

- 是否明确说明内容仅用于学习研究。
- 是否避免个性化投资建议和价格预测。
- 是否区分静态知识、用户提供信息、需要实时数据的信息。
- 是否包含主要风险维度。
- 是否结构完整且便于学习。

推荐配置：

```text
max_rounds = 2
pass_score_threshold = 0.9
```

### 3.3 Finance QA

适用性：中。

原因：

- 如果是概念解释、学习型问答，Reflection 很有价值。
- 如果问题需要实时数据，而系统不支持实时数据，应该由 `InvestoryPolicyGate` 在执行前拒绝或澄清，不应该靠 Reflection 事后补救。
- 如果问题涉及具体投资建议，仍应由策略门前置拦截。

适合 Reflection 的 QA 类型：

- 金融概念解释。
- 投资产品机制说明。
- 风险概念、财报指标、资产类别对比。
- 用户提供材料内的信息问答。

不适合依赖 Reflection 的 QA 类型：

- “今天能买吗？”
- “现在价格是多少？”
- “给我推荐一只股票。”
- “这个组合该不该调仓？”

结论：Finance QA 可以加 Reflection，但必须在 Policy Gate 之后，只验收表达质量、完整性和安全边界，不能用来替代前置合规判断。

### 3.4 入口路由决策

适用性：低到中。

原因：

- 路由属于执行前决策，已经有 `confidence` 和低置信度兜底。
- 对每一次路由都做 Reflection 会增加延迟和成本。
- 更合理的做法是只在低置信度、边界输入或测试离线评估中使用“二次检查”。

可行做法：

- 线上默认不对所有路由做 Reflection。
- 对 `confidence` 接近阈值的结果做轻量二次评估。
- 离线测试集中用 Reflection 检查路由 prompt 的稳定性。

## 4. 不建议使用 Reflection 的场景

以下场景不适合或不应该优先用 Reflection：

| 场景 | 原因 | 推荐处理 |
|---|---|---|
| 缺少必填输入 | Reflection 没有足够上下文可改进 | `ASK_FOR_MISSING_INPUT` |
| 投资建议请求 | 需要前置拒答，不应先生成再修正 | `REFUSE_AND_REDIRECT` |
| 需要实时数据但不支持 | 事实基础缺失，不能靠模型自检补齐 | 前置能力检查 |
| 高风险动作审批 | Reflection 是事后验收，不是审批流 | Plan / 用户确认 |
| 纯规则可验证输出 | 用代码校验更便宜、更稳定 | Deterministic validator |

原则：能用规则确定的，不交给 LLM 反思；涉及合规边界的，优先前置拦截。

## 5. 推荐的 Investory 落地架构

建议把 Reflection 做成独立的“输出验收层”，不要嵌进每个业务 handler。

推荐流程：

```text
User Input
  -> InvestoryPolicyGate
  -> LearningEntryRouter
  -> Task Handler
  -> ReflectionEvaluator
  -> Optional Reviser
  -> Final Response
```

建议新增或预留的抽象：

```text
ReflectionCriteria
ReflectionCritique
ReflectionResult
ReflectionEvaluator
ReflectionReviser
ReflectionRunner
```

结构化输出建议：

| 字段 | 类型 | 说明 |
|---|---|---|
| `passed` | `bool` | 是否通过验收 |
| `score` | `float` | 0 到 1 的质量分 |
| `issues` | `list[str]` | 给人看的问题说明 |
| `suggestions` | `list[str]` | 给模型执行的修改建议 |
| `safety_flags` | `list[str]` | 可选，记录越界风险 |
| `final_text` | `str` | 最终输出 |
| `rounds` | `int` | 实际迭代轮次 |

符合本项目“Typed Constants Over Raw Strings”规则的实现建议：

- 用 `str, Enum` 定义反思任务类型、评估结果、安全标记。
- 用模块级常量定义 prompt 文件名、metadata key、默认阈值。
- 不要在 handler 中散落 `"summary"`、`"brief"`、`"investment_advice"` 等业务字符串。

示例枚举方向：

```python
class ReflectionTarget(str, Enum):
    LEARNING_MATERIAL_SUMMARY = "learning_material_summary"
    INSTRUMENT_BRIEF = "instrument_brief"
    FINANCE_QA = "finance_qa"


class ReflectionSafetyFlag(str, Enum):
    INVESTMENT_ADVICE_RISK = "investment_advice_risk"
    UNSUPPORTED_REALTIME_DATA = "unsupported_realtime_data"
    HALLUCINATION_RISK = "hallucination_risk"
```

## 6. Reflection Criteria 设计建议

不同任务不应共用同一套泛化标准。建议按任务注册 criteria。

### 6.1 Summary Criteria

```text
- 覆盖材料核心主题和关键结论。
- 不添加材料外事实。
- 保留重要术语和必要上下文。
- 结构清晰，适合学习复习。
- 不输出投资建议。
```

### 6.2 Instrument Brief Criteria

```text
- 明确标的或金融工具的基本属性。
- 区分静态说明、用户提供信息、需要实时数据的信息。
- 覆盖主要风险和不确定性。
- 不给出买卖建议、收益承诺或价格预测。
- 输出结构适合学习用途。
```

### 6.3 Finance QA Criteria

```text
- 直接回答用户的学习型问题。
- 概念解释准确、边界清楚。
- 对缺失上下文做出说明。
- 不假装拥有未提供的实时数据。
- 不输出个性化投资建议。
```

## 7. 可行性分析

### 技术可行性

可行性：高。

理由：

- 项目已在路由层使用 Pydantic 结构化输出，Reflection 的 `Critique` 模型可以沿用同一方式。
- 现有 `RequestRunner` 可以承载“评估”和“改写”两类 LLM 调用。
- 当前 `InvestoryPolicyGate` 已经把合规边界前置，Reflection 可以专注质量验收。

主要工程工作：

- 增加 reflection prompt。
- 增加 Pydantic 输出模型。
- 增加任务到 criteria 的注册表。
- 在 summary、brief、QA handler 后挂接 ReflectionRunner。
- 增加单元测试和少量端到端测试。

### 产品可行性

可行性：中到高。

收益：

- 摘要和简介输出更稳定。
- 安全边界有第二道检查。
- 用户能看到更一致的结构和质量。
- 后续可以记录 `issues` 做 prompt 迭代依据。

代价：

- 每轮至少增加一次评估调用；未通过还会增加一次改写调用。
- 响应延迟和 LLM 成本会上升。
- 如果 criteria 互相冲突，会出现“反复改不好”的情况。

### 合规可行性

可行性：中。

Reflection 能增强安全，但不能作为唯一合规机制。

原因：

- LLM 自评不是确定性合规判定。
- 投资建议、实时数据能力、用户确认等问题必须由 `InvestoryPolicyGate` 前置处理。
- Reflection 更适合做“表达层和完整性层”的二次保险。

## 8. 推荐落地优先级

### Phase 1：离线评估，不进入线上链路

目标：验证 criteria 是否有效。

做法：

- 选取现有 summary、brief、QA 的样例输出。
- 用 ReflectionEvaluator 只打分、不改写。
- 人工检查 `issues` 是否合理。
- 调整 criteria 和 prompt。

适合先做，因为不会影响线上响应延迟。

### Phase 2：只对 Summary 开启自动改写

目标：在低风险生成任务中验证闭环。

建议：

- `max_rounds = 2`
- 首轮不通过才进入 revise。
- 最终仍不通过时返回最后版本，但 metadata 记录 `passed=false` 和 `issues`。

### Phase 3：Instrument Brief 加安全型 Reflection

目标：降低越界表达和结构遗漏。

建议：

- 分离质量 criteria 和安全 criteria。
- 安全 criteria 未通过时优先改写为学习型表达。
- 对疑似投资建议输出保守降级，不做强行润色。

### Phase 4：QA 按问题类型选择性启用

目标：控制成本。

建议：

- 概念解释类 QA 开启。
- 简短事实类 QA 可跳过。
- 低置信度或边界问题开启安全检查。

## 9. 实施风险与控制手段

| 风险 | 表现 | 控制手段 |
|---|---|---|
| 成本增加 | 每次生成后多 1 到 3 次 LLM 调用 | 只对高价值任务开启，限制 `max_rounds` |
| 延迟增加 | 用户等待时间变长 | Summary/Brief 开启，短 QA 跳过 |
| 自评不可靠 | 模型给自己放水 | criteria 具体化，加入代码规则校验 |
| 改写引入新幻觉 | revise 添加原文没有的信息 | prompt 要求“不添加输入外事实”，评估检查 hallucination risk |
| 合规边界后置 | 先生成违规内容再修正 | Policy Gate 必须前置，Reflection 只做二次保险 |
| 标准冲突 | 分数卡在中高位但无法通过 | 记录 criteria 命中情况，拆分或降级冲突标准 |

## 10. 对当前项目的结论

Reflection 适合 Investory，但应该“窄范围、后置、可观测”地引入。

推荐结论：

- 优先用于 `learning_material_summary`，这是收益最高、风险最低的场景。
- 第二优先级用于 `instrument_brief`，重点检查结构完整性和投资建议边界。
- `finance_qa` 只对学习型长回答启用，不对所有问答默认启用。
- 不建议用 Reflection 替代 `InvestoryPolicyGate`、低置信度路由兜底或实时数据能力检查。
- 工程上应做成独立 runtime 组件，并通过 typed enum、Pydantic model、prompt registry 管理，避免业务字符串散落。

最小可行版本：

```text
ReflectionEvaluator
  -> 输入：task_type, user_input, draft, criteria
  -> 输出：passed, score, issues, suggestions, safety_flags

ReflectionRunner
  -> 若 passed：返回 draft
  -> 若 failed 且 rounds < max_rounds：调用 Reviser
  -> 若达到 max_rounds：返回最后版本并记录 critique
```

这条路径与当前 Investory 的结构最兼容：前置由 `InvestoryPolicyGate` 控风险，中间由 router/handler 执行业务，后置由 Reflection 做质量验收。
