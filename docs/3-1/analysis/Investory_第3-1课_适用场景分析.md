# Investory 第 3-1 课适用场景分析（工具发现、调用与 MCP 协同）

参考材料：

```text
C:\Users\hy120\Downloads\zhihullm\agent\pre\第 3 章：工具 & MCP 接入（2 课）\第 3-1 课：工具发现、调用与 MCP 协同\第 3-1 课：工具发现、调用与 MCP 协同.md
```

参考 Investory 当前代码：

```text
src/investory/agent_core/runtime/decision_flow.py
src/investory/agent_core/runtime/decision_planner.py
src/investory/agent_core/actions/router.py
src/investory/agent_core/actions/executors.py
src/investory/agent_core/contracts/action_contract.py
src/investory/agent_core/tasks.py
src/investory/agent_core/task_models/instrument_brief.py
src/investory/gateway/routing.py
```

## 一、结论

`Investory` 在第 3-1 课最适合的方向，不是直接扩展“交易执行能力”，而是扩展“学习型外部信息接入能力”。

也就是：

```text
保持当前学习助手定位
-> 用工具补足“模型拿不到的事实数据”
-> 用统一工具治理保证可控、可审计、可替换
```

当前项目已经有决策与动作闭环：

```text
DecisionPlanner
-> TaskDecision
-> ActionValidator
-> ActionRouter
-> ActionExecutor
-> ActionResult
```

因此现在非常适合接入工具层（local / HTTP / MCP），把 `run_task_model` 前后的信息获取做成标准化 Tool 调用。

## 二、在你的项目里最适合的 4 类场景

## 场景 1：标的基础信息补全（最优先）

典型用户输入：

```text
帮我做一份 VTI 的学习简报。
```

当前问题：

- `instrument_brief` 依赖 `source_material`，如果用户没贴材料，就会进入 `ask_missing_fields`。

接工具后的目标：

- 当用户只给代码（如 `VTI`）时，先调用工具拉取公开资料摘要，再进入 `instrument_brief`。

工具形态建议：

- HTTP Tool：`fetch_instrument_profile`
- MCP Tool（后续）：`market_data.get_instrument_profile`

价值：

- 减少追问次数。
- 保持输出仍然是“学习简报”，不变成投资建议。

## 场景 2：术语问答的证据检索增强

典型用户输入：

```text
解释一下这个基金的 tracking error，顺便告诉我最近披露口径。
```

当前问题：

- `finance_qa` 可以解释概念，但对“最新披露口径”这类事实信息缺少可靠来源。

接工具后的目标：

- 先检索资料来源（基金页、公告、教育文档），再让模型基于证据作答。

工具形态建议：

- HTTP Tool：`search_learning_sources`
- Local Tool：`normalize_source_snippets`
- MCP Resource（后续）：`compliance/education_policy_docs`

价值：

- 输出带来源与时间上下文。
- 降低幻觉和过时信息风险。

## 场景 3：学习材料摘要的批量预处理

典型用户输入：

```text
把这 5 篇 ETF 材料整理成学习要点。
```

当前问题：

- `learning_material_summary` 假设输入已准备好单段 `material_text`。

接工具后的目标：

- 使用本地工具先完成文本清洗、分段、去重、长度裁剪，再喂给任务模型。

工具形态建议：

- Local Tool：`chunk_materials`
- Local Tool：`deduplicate_snippets`

价值：

- 稳定模型输入长度与质量。
- 提升长材料场景的一致性。

## 场景 4：高风险请求的受控分流

典型用户输入：

```text
现在能不能直接告诉我买不买这只基金。
```

当前状态：

- 已有 `refuse_investment_advice` 动作。

接工具后的目标：

- 拒绝后自动调用“替代路径工具”，给用户学习框架与资料请求模板。

工具形态建议：

- Local Tool：`build_learning_checklist`
- MCP Prompt/Template（后续）：`risk_notice_templates`

价值：

- 拒绝不终止对话，而是引导到可执行学习步骤。

## 三、Tools、MCP、Skills 在 Investory 中的边界

在你的项目中建议这样落边界：

- Tool：原子能力（查资料、检索、清洗、聚合）。
- MCP：对外部工具/资源的标准接入层（发现、调用、鉴权、版本化）。
- Skill：面向任务编排的可复用策略包（例如“ETF 学习简报技能”）。

对应关系可以先定为：

```text
Skill 编排多个 Tool
Tool 既可以是本地/HTTP，也可以来自 MCP Server
DecisionFlow 只感知统一 ToolContract，不关心底层来源
```

## 四、当前阶段不建议优先接入的场景

以下场景与项目定位冲突或工程成本过高，建议放后：

- 直接交易下单、调仓、止盈止损执行。
- 账户资产读写、券商 API 高权限操作。
- 实时高频行情驱动的自动化策略。

原因：

- 与“投资学习助手”定位不一致。
- 权限、审计、风控要求显著更高。

## 五、第 3-1 课在 Investory 的落地优先级

建议按这个顺序推进：

1. 先接 HTTP 工具：标的基础资料获取 + 学习资料检索。
2. 再补本地工具：文本清洗、分块、去重。
3. 再引入 MCP：把多数据源工具统一成可发现/可治理注册表。
4. 最后做 Skill：把“简报生成”“术语学习”“风险分流”沉淀为可复用流程。

这样能在不改变你当前架构主干的前提下，把第 3-1 课能力自然接到现有 `DecisionFlow` 上。
