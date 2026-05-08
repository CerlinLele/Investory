# Investory 第 2-1 课适用场景分析

参考材料：

```text
pre/第 2 章：规划、决策、行动与结构化输出（2 课）/第 2-1 课：从任务理解到动作决策/第 2-1 课：从任务理解到动作决策.md
pre/第 2 章：规划、决策、行动与结构化输出（2 课）/第 2-1 课：从任务理解到动作决策/codex/Codex 动作决策链路源码定位.md
```

参考 Investory 当前代码：

```text
src/investory/agent_core/tasks.py
src/investory/agent_core/task_models/finance_qa.py
src/investory/agent_core/task_models/learning_material_summary.py
src/investory/agent_core/runtime/minimal_flow.py
src/investory/agent_core/contracts/flow_state.py
src/investory/gateway/routing.py
src/investory/gateway/schemas.py
```

## 一、结论

`Investory` 最适合做的不是“投资决策 agent”，而是“投资学习任务助理”。

第 2-1 课引入的核心能力是：

```text
从用户自然语言输入中理解任务
-> 判断下一步动作
-> 输出结构化 action
-> 由系统校验和路由
-> 再交给具体 executor 执行
```

这和 `Investory` 的项目定位非常匹配，因为投资学习类产品经常遇到这类输入：

```text
帮我看看这只 ETF 值不值得买。
```

这句话表面上是投资决策请求，但系统不应该直接给买卖建议。更合理的动作决策是：

```text
识别为高风险投资建议请求
-> 收束为学习型分析
-> 解释可以从哪些维度理解 ETF
-> 如果材料不足，追问用户提供基金说明、持仓、费用、跟踪指数等信息
```

所以 `Investory` 在第 2-1 课最适合讲的不是“模型如何给答案”，而是：

```text
模型如何在风险边界内判断下一步动作。
```

## 二、当前 Investory 已经适合的场景

当前代码已经支持两个明确任务：

```text
finance_qa
learning_material_summary
```

代码位置：

```text
src/investory/agent_core/tasks.py
```

当前 `gateway/routing.py` 还提供了两个公开别名：

```text
qa -> finance_qa
summary -> learning_material_summary
```

因此，当前阶段最适合的场景有两类。

## 三、场景 1：投资理财概念问答

对应任务：

```text
finance_qa
```

代码位置：

```text
src/investory/agent_core/task_models/finance_qa.py
```

适合的用户输入：

```text
根据这段基金说明，解释一下最大回撤是什么意思。

这篇文章里提到久期，能不能用新手能理解的话解释一下？

ETF 的跟踪误差为什么重要？

基金费率里的管理费、托管费、销售服务费分别是什么？
```

当前 `FinanceQAInput` 要求两个字段：

```text
material_text
question
```

当前 `FinanceQAResult` 输出：

```text
answer
concept_explanation
evidence
common_misunderstandings
risk_notice
uncertainty
```

这个场景适合当前阶段，因为它满足几个条件：

- 用户目标明确：解释一个概念或回答一个学习问题。
- 输入边界清楚：有材料和问题。
- 输出可以结构化：答案、解释、依据、误区、风险提示、不确定性。
- 风险容易控制：可以强制保留 `risk_notice` 和 `uncertainty`。

第 2-1 课里，这类请求通常应该被 planner 判断为：

```json
{
  "action": "answer_finance_question",
  "params": {
    "task_name": "finance_qa"
  },
  "risk_level": "low",
  "need_user_confirmation": false
}
```

## 四、场景 2：财经材料摘要与学习待办

对应任务：

```text
learning_material_summary
```

代码位置：

```text
src/investory/agent_core/task_models/learning_material_summary.py
```

适合的用户输入：

```text
请帮我总结这篇 ETF 入门文章，并列出后续学习事项。

帮我整理这段基金介绍，提炼关键概念和风险点。

这篇宏观分析我看不懂，帮我整理成学习笔记。

请把这段财报学习材料整理成摘要、关键概念和待办。
```

当前 `LearningMaterialSummaryInput` 要求：

```text
material_text
```

当前 `LearningMaterialSummaryResult` 输出：

```text
summary
key_concepts
key_takeaways
risks
todos
uncertainty
```

这个场景非常适合作为 Investory 的主 demo，因为它天然能展示：

- 投资学习助手的业务定位；
- 结构化输出的价值；
- 风险提示和不确定性说明；
- 从单次请求继续扩展到学习计划、记忆和复盘。

第 2-1 课里，这类请求可以被 planner 判断为：

```json
{
  "action": "summarize_learning_material",
  "params": {
    "task_name": "learning_material_summary"
  },
  "risk_level": "low",
  "need_user_confirmation": false
}
```

## 五、第 2-1 课引入后最应该新增的场景

当前 `Investory` 已经有最小任务执行器和最小编排流程：

```text
TaskExecutor
-> MinimalTaskFlow
   -> prepare_context
   -> call_model
   -> finalize_result
```

代码位置：

```text
src/investory/agent_core/runtime/task_executor.py
src/investory/agent_core/runtime/minimal_flow.py
src/investory/agent_core/contracts/flow_state.py
```

但当前流程还是线性的。它还不会自己判断：

```text
这是问答？
这是摘要？
这是学习计划？
这是高风险投资建议？
这是信息不足，需要追问？
```

第 2-1 课最适合在当前架构上新增一个结构化决策层。

建议新增的动作类型：

```text
answer_finance_question
summarize_learning_material
ask_missing_fields
refuse_investment_advice
convert_to_learning_framework
suggest_study_plan
query_instrument_info_future
```

其中当前可以直接落地的是：

```text
answer_finance_question
summarize_learning_material
ask_missing_fields
refuse_investment_advice
convert_to_learning_framework
```

后续工具接入后再落地：

```text
query_instrument_info_future
```

## 六、场景 3：自动判断用户想做 QA 还是 Summary

适合输入：

```text
这篇文章我看不懂，帮我解释里面讲的最大回撤。
```

这句话同时包含材料整理和概念问答。planner 应该判断用户当前核心意图。

可能动作：

```json
{
  "action": "answer_finance_question",
  "reason": "用户明确要求解释材料中的最大回撤概念，而不是总结整篇材料。",
  "params": {
    "task_name": "finance_qa",
    "required_fields": ["material_text", "question"]
  },
  "need_user_confirmation": false
}
```

适用价值：

- 当前 gateway 要求用户传 `task_type`。
- 第 2-1 课后可以让系统先判断 task route。
- 用户不需要知道内部任务名是 `finance_qa` 还是 `learning_material_summary`。

对应课程概念：

```text
任务理解 -> 动作决策 -> 路由到 executor
```

## 七、场景 4：输入信息不足时追问用户

适合输入：

```text
帮我分析一下这个基金。
```

这类请求不应该直接进入 `finance_qa` 或 `learning_material_summary`，因为缺少：

- 基金名称或代码；
- 用户想了解的问题；
- 材料文本；
- 分析目标；
- 数据日期。

planner 应该输出：

```json
{
  "action": "ask_missing_fields",
  "reason": "用户表达了基金学习需求，但没有提供基金资料、基金代码或具体问题。",
  "params": {
    "missing_fields": ["instrument_name_or_code", "question_or_goal", "source_material"]
  },
  "user_message": "可以。请先提供基金名称或代码，并说明你想了解费用、风险、持仓、历史表现还是基本概念。",
  "need_user_confirmation": false
}
```

适用价值：

- 避免模型凭空分析。
- 避免系统直接输出投资建议。
- 为后续工具查询或材料摘要准备必要字段。

这和第 2-1 课里的“补齐申请字段 -> 查询规则 -> 生成表单”是同一类模式。

在 Investory 中可以改写为：

```text
补齐投资学习字段
-> 判断任务类型
-> 执行 QA / Summary / 未来的 instrument brief
```

## 八、场景 5：把高风险投资决策请求收束成学习任务

适合输入：

```text
现在能不能买这只 ETF？

帮我决定买 A 基金还是 B 基金。

我有 10 万块，应该怎么配置？

这只股票下周会涨吗？
```

这些请求不适合直接回答。

原因：

- 它们接近个性化投资建议；
- 可能涉及择时、仓位、买卖建议；
- 当前项目定位明确不是投顾系统；
- 当前代码没有行情、持仓、风险测评、合规审查等支撑。

更合理的动作是：

```json
{
  "action": "convert_to_learning_framework",
  "reason": "用户请求直接投资决策，超出 Investory 的学习助手边界。",
  "params": {
    "blocked_decision_type": "buy_sell_or_allocation_advice",
    "safe_alternative": "explain_analysis_framework"
  },
  "user_message": "我不能替你判断是否买入或配置比例，但可以帮你用学习框架理解这只产品的风险、费用、跟踪指数和适用场景。",
  "need_user_confirmation": false
}
```

适用价值：

- 强化 Investory 的安全边界。
- 把危险请求转成学习请求。
- 让产品定位更清晰。

这类场景最适合第 2-1 课讲：

```text
模型输出不是控制流。
planner 给出 action 后，系统还要检查风险边界。
```

## 九、场景 6：基金或 ETF 基础信息整理

当前项目定义中第一版 MVP 包含：

```text
instrument_brief
```

但当前代码还没有这个任务类型，当前只实现了：

```text
finance_qa
learning_material_summary
```

所以这个场景适合放在第 2-1 课后的下一步，而不是当前直接声称已经支持。

适合输入：

```text
帮我整理一下 510300 这只 ETF 的基础信息。

帮我看一下这只基金的费用、风险和跟踪标的。

请把这段基金说明整理成基础信息卡片。
```

如果用户已经提供材料，可以先走 `learning_material_summary`。

如果用户只提供代码，需要未来工具层支持：

```text
query_instrument_info
```

第 2-1 课中的动作可以先设计为：

```json
{
  "action": "query_instrument_info_future",
  "reason": "用户提供了基金或 ETF 代码，但当前系统尚未接入基金资料工具。",
  "params": {
    "instrument_code": "510300"
  },
  "user_message": "当前还没有接入基金资料工具。你可以先粘贴基金说明，我可以帮你整理费用、风险和学习要点。",
  "need_user_confirmation": false
}
```

这个场景适合后续第 3 章工具接入。

## 十、场景 7：学习计划生成

项目定义里第一版 MVP 也包含：

```text
study_plan
```

当前代码还没有 `study_plan` 任务，但 `learning_material_summary` 已经能输出 `todos`。

所以第 2-1 课可以先把它作为“动作决策设计场景”，后续再实现任务模型。

适合输入：

```text
我想两周入门 ETF，帮我安排学习计划。

我刚看完这篇基金文章，接下来应该学什么？

帮我按新手水平规划一个资产配置入门路径。
```

可能动作：

```json
{
  "action": "suggest_study_plan",
  "reason": "用户希望得到学习路径，而不是单篇材料摘要。",
  "params": {
    "topic": "ETF 入门",
    "duration": "2 weeks",
    "level": "beginner"
  },
  "need_user_confirmation": false
}
```

如果当前还没有实现 `study_plan` executor，可以先收束为：

```text
返回学习计划草稿，或提示该能力将在后续任务类型中实现。
```

## 十一、场景 8：学习复盘与风险认知训练

这个场景更适合后续状态层和 memory，但可以在第 2-1 课先定义动作。

适合输入：

```text
我学完了 ETF、指数基金和最大回撤，帮我复盘一下。

我总是看到上涨就想买，帮我分析这种风险。

帮我做一个风险偏好学习问卷。
```

可能动作：

```json
{
  "action": "start_risk_learning_review",
  "reason": "用户希望进行风险认知或学习复盘，属于状态化学习任务。",
  "params": {
    "review_type": "risk_awareness",
    "known_topics": ["ETF", "index_fund", "drawdown"]
  },
  "need_user_confirmation": false
}
```

当前阶段不建议直接实现完整复盘系统，因为它需要：

- 学习历史；
- session transcript；
- 用户偏好；
- 复盘记录；
- 风险问卷状态。

但它很适合作为后续第 9 章状态管理和 memory 的业务场景。

## 十二、不适合 Investory 的场景

以下场景不适合当前 Investory，或者必须强制收束。

### 1. 直接投资建议

不适合输入：

```text
我现在该买什么？
这只股票能买吗？
我该买多少仓位？
明天要不要卖？
```

建议动作：

```text
refuse_investment_advice
或 convert_to_learning_framework
```

### 2. 实时行情判断

不适合输入：

```text
今天这个 ETF 为什么涨？
现在价格是不是低估？
这只基金今天适合买入吗？
```

原因：

- 当前没有实时行情工具；
- 没有数据时间标注机制；
- 容易变成择时建议。

建议动作：

```text
ask_missing_fields
或 convert_to_learning_framework
```

如果未来接入工具，也应该输出：

```text
仅做信息整理，不做买卖结论。
```

### 3. 个性化资产配置

不适合输入：

```text
我有 50 万，帮我配置基金组合。

我今年 30 岁，应该买多少股票基金？
```

原因：

- 涉及个人财务状况；
- 涉及风险承受能力；
- 需要合规投顾资格和完整适当性评估。

建议动作：

```text
refuse_investment_advice
```

安全替代：

```text
解释资产配置的一般学习框架和风险维度。
```

### 4. 自动交易或下单

不适合输入：

```text
帮我自动买入这只基金。

到某个价格提醒我卖出。
```

当前系统不应该做交易执行面。

## 十三、建议的最小 action schema

第 2-1 课可以先给 Investory 定义一个最小动作契约：

```json
{
  "action": "answer_finance_question",
  "reason": "用户正在询问投资学习概念。",
  "confidence": 0.9,
  "risk_level": "low",
  "params": {
    "task_name": "finance_qa",
    "required_fields": ["material_text", "question"]
  },
  "missing_fields": [],
  "user_message": "我会根据你提供的材料解释这个概念，并标注风险和不确定性。",
  "need_user_confirmation": false
}
```

字段建议：

| 字段 | 作用 |
|---|---|
| `action` | 下一步动作，只能来自枚举 |
| `reason` | 决策理由，便于日志和调试 |
| `confidence` | 任务判断置信度 |
| `risk_level` | 投资学习场景的风险等级 |
| `params` | 交给 executor 的参数 |
| `missing_fields` | 信息不足时需要补齐的字段 |
| `user_message` | 可展示给用户的说明 |
| `need_user_confirmation` | 是否需要用户确认后再执行 |

建议动作枚举：

```text
answer_finance_question
summarize_learning_material
ask_missing_fields
refuse_investment_advice
convert_to_learning_framework
suggest_study_plan
query_instrument_info_future
```

## 十四、建议的第 2-1 课落地方式

当前流程是：

```text
TaskExecutor
-> MinimalTaskFlow
   -> prepare_context
   -> call_model
   -> finalize_result
```

第 2-1 课后可以演进为：

```text
Gateway / CLI
-> DecisionPlanner
   -> classify intent
   -> validate fields
   -> output action schema
-> ActionRouter
   -> finance_qa
   -> learning_material_summary
   -> ask_missing_fields
   -> refuse / convert_to_learning_framework
-> MinimalTaskFlow
   -> prepare_context
   -> call_model
   -> finalize_result
```

也可以先做更小一步：

```text
POST /tasks/decide
-> 返回 TaskDecision
```

不立即接 executor。

这样第 2-1 课可以先验证：

- 用户自然语言能否被稳定分类；
- 投资建议请求能否被识别并收束；
- 信息不足时能否输出追问字段；
- `action` 是否稳定来自枚举；
- `params` 是否能被后续 executor 消费。

## 十五、最推荐作为第 2-1 课 demo 的 5 个输入

### Demo 1：明确 QA

```text
根据这段基金说明，解释一下最大回撤是什么意思。
```

期望动作：

```text
answer_finance_question
```

### Demo 2：明确 Summary

```text
请帮我总结这篇 ETF 入门文章，并列出后续学习事项。
```

期望动作：

```text
summarize_learning_material
```

### Demo 3：信息不足

```text
帮我分析一下这只基金。
```

期望动作：

```text
ask_missing_fields
```

### Demo 4：投资建议越界

```text
这只 ETF 现在能买吗？
```

期望动作：

```text
convert_to_learning_framework
```

### Demo 5：未来工具场景

```text
帮我整理 510300 的费用、风险和跟踪指数。
```

期望动作：

```text
query_instrument_info_future
```

当前替代动作：

```text
ask_missing_fields
```

或提示用户粘贴基金资料。

## 十六、一句话总结

`Investory` 最适合第 2-1 课的场景，是把用户混杂、模糊甚至高风险的投资相关请求，先转成受控的结构化动作决策，再由系统决定是执行 `finance_qa`、执行 `learning_material_summary`、追问信息，还是收束为学习框架。它不适合直接做买卖建议、择时判断、个性化资产配置或自动交易。
