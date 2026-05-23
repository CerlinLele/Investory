# Investory 工具封装分析

## 结论

当前项目最适合先封装“只读、可校验、可 mock 的投资学习辅助工具”，而不是直接做通用 agent 工具循环或交易执行工具。

原因是现有 runtime 已经具备清晰的任务执行骨架：

- `TaskSpec` 定义任务名、prompt、输入模型、输出模型。
- `RequestRunner` 使用 LangChain `with_structured_output` 做结构化模型调用。
- `TaskExecutionPipeline` 负责输入校验、prompt 构建、模型调用、结果封装。
- `LearningQaOrchestrationFlow` 使用 LangGraph 做动作编排。
- `ActionRouter` 当前只支持 `ask_missing_fields`、`run_task_model`、`refuse_investment_advice` 三类动作。

但项目还没有真正的工具抽象层。`config.py` 中已经有 `mock_tools_enabled`，`gateway` 包注释也提到 external providers and tools，说明设计方向已经预留了工具接入位置，只是尚未落地。

## 当前架构判断

### 已经稳定的部分

1. 任务边界清楚

   当前任务包括：

   - `finance_qa`
   - `learning_material_summary`
   - `instrument_brief`

   这些任务都依赖 Pydantic input/output model，适合接入结构化工具结果。

2. 安全边界明确

   `instrument_brief.md` 明确要求只基于用户提供的 `source_material`，不推断实时价格、最新费率、最新持仓等当前数据。这说明现阶段产品定位是投资学习助手，而不是投资建议或交易助手。

3. 动作路由已经存在

   `LearningQaOrchestrationFlow` 已经有 planner -> validate -> route -> executor 的形状。未来工具可以作为新的 action 接入，也可以先作为 task 前置增强步骤接入。

### 还不适合直接做的部分

1. 不适合直接封装交易工具

   例如下单、调仓、买卖建议、仓位建议。这会突破现有风险提示和拒绝投资建议逻辑，也需要更严格的用户确认、合规审计和权限模型。

2. 不适合先做开放式浏览器工具

   当前输出模型强调 evidence、risk、uncertainty。如果直接让模型任意搜索网页，容易引入来源不可控、时效不可控、引用不可追踪的问题。

3. 不适合把工具直接塞进模型 tool calling

   现有系统不是多轮 tool loop，而是结构化单次模型调用 + 外层动作编排。直接改为模型自主调工具会影响 `RequestRunner`、错误处理、测试方式和任务契约。

## 推荐优先封装的工具

### 1. 标的资料读取工具

优先级：最高。

适合任务：

- `instrument_brief`
- `finance_qa`
- 未来的 fund/ETF/stock 学习任务

建议工具名：

- `lookup_instrument_profile`
- `fetch_instrument_factsheet`
- `resolve_instrument_identifier`

输入示例：

```json
{
  "instrument_name_or_code": "VTI",
  "market": "US",
  "preferred_sources": ["local_cache", "provider"]
}
```

输出建议：

```json
{
  "instrument_name_or_code": "VTI",
  "resolved_name": "Vanguard Total Stock Market ETF",
  "instrument_type": "ETF",
  "facts": [
    {
      "label": "Issuer",
      "value": "Vanguard",
      "source": "provider_name",
      "as_of": "2026-05-23"
    }
  ],
  "source_material": "...",
  "uncertainty": ["Holdings may change over time."]
}
```

这个工具最好先只做“资料补全”，不输出投资判断。

### 2. 金融术语解释工具

优先级：高。

适合任务：

- `finance_qa`
- `learning_material_summary`

建议工具名：

- `lookup_financial_concept`
- `explain_financial_term`

输入示例：

```json
{
  "term": "expense ratio",
  "audience_level": "beginner"
}
```

输出建议：

```json
{
  "term": "expense ratio",
  "plain_english": "The annual fee charged by a fund as a percentage of assets.",
  "related_terms": ["management fee", "ETF", "mutual fund"],
  "common_misunderstandings": ["A lower expense ratio does not guarantee better returns."]
}
```

这个工具可以先基于本地知识库或静态 JSON，不依赖外部 API，测试成本低。

### 3. 学习材料解析工具

优先级：高。

适合任务：

- `learning_material_summary`
- `finance_qa`
- `instrument_brief`

建议工具名：

- `extract_learning_material_facts`
- `split_material_sections`
- `extract_risk_statements`

职责：

- 从用户粘贴的材料中提取事实、风险、数字、日期、产品名称。
- 把 source material 变成结构化 evidence，再交给模型生成解释。

这比让模型直接处理长文本更稳定，也更容易测试。

### 4. 只读行情快照工具

优先级：中。

适合未来任务，不建议立即接入现有 `instrument_brief` 默认路径。

建议工具名：

- `get_market_snapshot`
- `get_price_snapshot`

限制：

- 只返回当前或历史价格事实。
- 必须带 `as_of` 时间。
- 不输出涨跌判断、买卖建议、目标价或仓位建议。

输出中必须包含：

- `price`
- `currency`
- `as_of`
- `provider`
- `delay_notice`
- `uncertainty`

### 5. 新闻或公告检索工具

优先级：中低。

建议工具名：

- `search_instrument_news`
- `fetch_company_announcements`
- `search_sec_filings`

建议先做白名单来源，而不是开放式网页搜索：

- SEC filings
- issuer factsheet
- exchange announcements
- official fund provider pages

开放网页搜索可以晚一点做，因为它对来源质量、去重、引用和过期内容处理要求更高。

### 6. 投资建议拒绝与重写工具

优先级：中。

当前已有 `refuse_investment_advice` action，但可以封装成更系统的安全工具。

建议工具名：

- `classify_investment_advice_request`
- `rewrite_to_learning_question`

用途：

- 判断用户是否在请求买卖、持仓、时机、收益承诺。
- 把不合规问题改写成学习型问题。

示例：

```json
{
  "original_question": "Should I buy VTI today?",
  "classification": "investment_advice",
  "safe_rewrite": "What factors should I understand before evaluating a broad-market ETF like VTI?"
}
```

## 建议的落地顺序

### Phase 1: 本地工具抽象

先新增 `agent_core/tools` 或 `gateway/tools`，不要马上改变模型调用方式。

建议结构：

```text
src/investory/agent_core/tools/
  __init__.py
  contracts.py
  registry.py
  mocks.py
  financial_concepts.py
  material_extraction.py
  instrument_profile.py
```

核心接口：

```python
class ToolExecutor(Protocol):
    name: str

    def run(self, payload: BaseModel) -> BaseModel:
        ...
```

先接入 `mock_tools_enabled`，保证没有外部 API 也能测试。

### Phase 2: 作为任务前置增强接入

先不要做 LLM tool calling。建议在 `TaskExecutionPipeline` 前增加可选 enrichment：

```text
payload -> input validation -> optional tool enrichment -> prompt build -> model call
```

例如 `instrument_brief` 可以把：

```json
{
  "instrument_name_or_code": "VTI"
}
```

增强成：

```json
{
  "instrument_name_or_code": "VTI",
  "source_material": "...provider or mock factsheet..."
}
```

这条路径对现有架构改动最小，也符合当前 `TaskSpec` + Pydantic 的风格。

### Phase 3: 把工具变成 action

当工具数量变多后，再扩展 action contract：

```python
RUN_TOOL = "run_tool"
```

并新增：

```python
class RunToolExecutor:
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        ...
```

这时 planner 可以决定：

- 缺字段：`ask_missing_fields`
- 需要资料：`run_tool`
- 资料齐全：`run_task_model`
- 涉及投资建议：`refuse_investment_advice`

### Phase 4: 再考虑模型自主 tool calling

只有当你需要多步推理和多次工具调用时，才值得让模型直接控制 tools。

例如：

```text
用户问题 -> planner -> model chooses tools -> tool results -> final structured answer
```

这会明显增加 runtime 复杂度，需要同步升级：

- tool call loop
- tool result schema
- max tool call limit
- source citation
- timeout/retry
- tool error normalization
- audit log

## 不建议封装的工具

短期不建议封装：

- `place_order`
- `rebalance_portfolio`
- `recommend_buy_sell`
- `calculate_position_size`
- `predict_price_target`
- `rank_best_stocks_to_buy`

这些工具会让项目从投资学习助手变成投资建议或交易执行系统，和当前 prompt、安全边界、错误模型都不匹配。

## 推荐的最小可行工具组合

第一批只做三个工具最合适：

1. `lookup_financial_concept`

   本地静态知识库，服务 `finance_qa` 和 `learning_material_summary`。

2. `extract_learning_material_facts`

   从用户材料中抽取事实、风险、数字和不确定性。

3. `lookup_instrument_profile`

   支持 mock 返回，后续替换成真实 provider。

这三个工具都符合当前项目定位：

- 只读
- 教育用途
- 可结构化校验
- 可 mock
- 不触碰交易执行
- 不直接给投资建议

## 推荐实现边界

工具输入输出必须用 Pydantic model。

工具结果必须包含来源和时间：

```python
class ToolSource(BaseModel):
    provider: str
    source_url: str | None = None
    as_of: str | None = None
```

工具错误不要直接抛给 API 用户，应转换为现有 `TaskError` 或工具专用错误类型。

工具应该支持 timeout 和 retry，但不要复用 LLM retry policy。外部数据 provider 的失败模式和模型调用不同，需要单独封装。

工具执行应该默认只读，不持久化用户敏感数据。

## 最终建议

当前最合理的方向是：

1. 先封装本地/Mock 工具层。
2. 先让工具服务于 `instrument_brief` 的资料补全和 `finance_qa` 的概念解释。
3. 先走 pipeline enrichment，不急着做模型 tool calling。
4. 工具稳定后再升级 `ActionContract`，让 planner 能显式选择 `run_tool`。
5. 保持“投资学习助手”的安全边界，不封装交易、买卖建议、仓位建议类工具。

这样做能最大程度复用现在的 `TaskSpec`、Pydantic schema、`ActionRouter` 和 `TaskExecutionPipeline`，同时把未来接真实数据源的入口提前设计出来。
