# Investory 投资文档审查助手 v0 路由迁移实施计划

## 1. 参考代码能看到的核心逻辑

参考目录：

```text
C:\Users\hy120\Downloads\zhihullm\agent\lecture\08. 实战——智能文档审查助手\scripts\v0_只路由
```

核心文件：

```text
doc_review/flows/router.py
doc_review/flows/review.py
review.py
review_framework.yaml
```

参考实现的 v0 主线是：

```text
doc_text + doc_type_hint
  -> classify_document
  -> doc_type + confidence_level + reason
  -> low confidence fallback to general
  -> select review framework by doc_type
  -> single pass review
  -> extracted_facts + findings + suggestions + summary
```

它的关键设计点不是 Agently 本身，而是这几个业务动作：

1. 只读取文档开头做路由，避免路由阶段消耗整篇文档。
2. 路由只判断文档类型，不审查内容质量。
3. 路由输出结构化字段：`doc_type`、`confidence_level`、`reason`。
4. 低置信度路由降级到通用审查框架。
5. 审查框架按文档类型配置，包含 `extract_focus` 和 `analyze_focus`。
6. v0 用一次综合审查跑通闭环，后续再拆成 Todo / Plan / Reflection。

## 2. Investory 不直接照搬的部分

Investory 当前已有自己的运行时边界：

```text
RequestRunner
TaskExecutionPipeline
TaskExecutor
LangGraph StateGraph
InvestoryPolicyGate
TodoExecutionRunner
Pydantic contracts
prompt_loader
FastAPI gateway
```

因此不建议把参考项目里的 `Agently`、`TriggerFlow`、`.output(...)` 调用方式直接搬进来。

迁移原则：

1. 参考它的业务流程，不引入新的 agent 框架依赖。
2. 结构化输出继续使用 Pydantic model。
3. LLM 调用继续走 `RequestRunner`。
4. flow 编排继续使用当前项目里的 LangGraph 风格。
5. 固定业务字符串使用 `str, Enum` 或模块级常量，遵守仓库规则。
6. 文档审查必须复用投资边界策略，不能生成买入、卖出、持仓、收益承诺或个性化配置建议。

## 3. 目标目录结构

当前已经为新 flow 预留了目录：

```text
src/investory/agent_core/runtime/flow/investment_document_review/
```

建议 v0 最终形成：

```text
src/investory/agent_core/contracts/
  investment_document_review_state.py

src/investory/agent_core/runtime/flow/investment_document_review/
  __init__.py
  document_review_actions.py
  document_review_rules.py
  document_review_router.py
  document_review_flow.py

src/investory/agent_core/prompts/flows/
  investment_document_review_router.md

src/investory/agent_core/prompts/tasks/
  investment_document_review_single_pass.md

src/investory/agent_core/task_models/
  investment_document_review.py

tests/
  test_investment_document_review_rules.py
  test_investment_document_review_router.py
  test_investment_document_review_flow.py
  test_investment_document_review_gateway_api.py
```

## 4. 参考实现到 Investory 的映射

| 参考实现 | Investory 落点 | 说明 |
|---|---|---|
| `DocType = Literal[...]` | `InvestmentDocumentType(str, Enum)` | 使用枚举，避免散落裸字符串 |
| `Confidence = Literal[...]` | `DocumentReviewRouteConfidence(str, Enum)` 或 `confidence: float` | 建议沿用 Investory 现有 router 的 `float` 置信度风格 |
| `classify_document(text, hint)` | `InvestmentDocumentReviewLLMRouter.route(payload)` | 使用 `RequestRunner` + Pydantic 输出 |
| `text[:600]` | `DOCUMENT_ROUTER_MAX_CHARS` | 模块级常量 |
| low confidence fallback | `DEFAULT_ROUTE_CONFIDENCE_THRESHOLD` | 低于阈值时降级为 `unknown` 或 `general_learning_material` |
| `REVIEW_FRAMEWORK` | `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE` | 先放 Python 常量，后续再考虑 YAML |
| `single_pass_review` | `investment_document_review_single_pass` task | v0 一次综合审查 |
| `review_document_v0` | `InvestmentDocumentReviewFlow.run` | LangGraph 编排 |

## 5. 文档类型设计

参考代码的类型是：

```text
contract
policy
tech_spec
general
```

Investory 的投资场景应改成：

```text
etf_factsheet
fund_prospectus
product_brochure
earnings_report
learning_material
unknown
```

建议第一版不要引入通用法律合同、公司政策、技术规格书类型，避免业务边界漂移。`unknown` 用于低置信度或材料不足，而不是强行审查。

## 6. v0 输入输出契约

### 6.1 输入字段

建议 gateway payload 支持：

```python
{
    "document_text": "...",
    "document_type_hint": "optional",
    "review_goal": "optional",
}
```

模块级常量：

```python
DOCUMENT_TEXT_FIELD = "document_text"
DOCUMENT_TYPE_HINT_FIELD = "document_type_hint"
REVIEW_GOAL_FIELD = "review_goal"
```

### 6.2 路由输出

```python
class InvestmentDocumentReviewRouteDecision(BaseModel):
    document_type: InvestmentDocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
```

### 6.3 审查输出

```python
class InvestmentDocumentReviewResult(BaseModel):
    document_type: InvestmentDocumentType
    extracted_facts: list[str]
    risk_findings: list[str]
    information_gaps: list[str]
    boundary_notes: list[str]
    summary: str
```

与参考代码相比，Investory 不建议使用泛化的 `suggestions` 字段。投资场景里 `suggestions` 容易滑向投资建议，应改成：

```text
information_gaps
boundary_notes
learning_next_steps
```

## 7. v0 Flow 编排

建议 v0 使用 LangGraph，节点保持少而清晰：

```text
InvestmentDocumentReviewFlow

START
  -> evaluate_policy_gate
  -> route_after_policy_gate
       missing/refusal -> build_missing_or_refusal_result
       complete        -> classify_document_type
  -> route_after_classification
       low confidence / unknown -> build_missing_input_result
       known type               -> build_review_framework
  -> run_single_pass_review
  -> build_final_result
END
```

第一版节点：

```python
class InvestmentDocumentReviewNode(str, Enum):
    EVALUATE_POLICY_GATE = "evaluate_policy_gate"
    CLASSIFY_DOCUMENT_TYPE = "classify_document_type"
    BUILD_REVIEW_FRAMEWORK = "build_review_framework"
    RUN_SINGLE_PASS_REVIEW = "run_single_pass_review"
    BUILD_FINAL_RESULT = "build_final_result"
    BUILD_MISSING_INPUT_RESULT = "build_missing_input_result"
    BUILD_REFUSAL_RESULT = "build_refusal_result"
```

## 8. Policy Gate 处理方式

不要直接把现有 `InvestoryPolicyGate` 原封不动复用到文档审查上，因为它现在服务于 learning entry，内部依赖：

```text
LearningEntryRoute
LearningEntryCandidateTaskType
learning_entry_rules
```

推荐做法：

1. 短期：在 `investment_document_review` 包内新增轻量规则函数，先检查 `document_text` 是否存在、是否包含明显投资建议请求、是否请求实时价格或收益预测。
2. 中期：抽出共享的投资安全规则模块，例如 `runtime/flow/investory_policy/`，让 learning entry 和 document review 都复用。
3. 长期：把 policy gate 做成业务无关的输入安全层，再由不同 flow 添加各自的 missing-field 和 routing 规则。

v0 可以先不做大重构，避免为了新 flow 牵动 learning entry。

## 9. Review Framework 设计

参考代码的 `review_framework.yaml` 可以借鉴，但 Investory v0 建议先用 Python 常量，便于类型检查和测试。

建议文件：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py
```

示例结构：

```python
DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE = {
    InvestmentDocumentType.ETF_FACTSHEET: DocumentReviewFramework(
        extract_focus=[...],
        analyze_focus=[...],
    ),
}
```

每种类型的审查重点：

| 文档类型 | 抽取重点 | 分析重点 |
|---|---|---|
| `etf_factsheet` | 标的指数、费用、资产配置、历史表现说明 | 风险披露、历史表现边界、费用影响 |
| `fund_prospectus` | 投资范围、费用、限制条款、赎回规则 | 风险因素、适用限制、信息缺口 |
| `product_brochure` | 产品结构、收益表述、适用条件 | 是否夸大收益、风险披露是否充分 |
| `earnings_report` | 收入、利润、现金流、管理层说明 | 不确定性、不能外推的结论、事实边界 |
| `learning_material` | 概念、机制、术语、示例 | 学习重点、材料内事实与外部推断边界 |
| `unknown` | 不执行正式审查 | 请求用户补充类型或材料上下文 |

## 10. Prompt 迁移计划

新增路由 prompt：

```text
src/investory/agent_core/prompts/flows/investment_document_review_router.md
```

要求：

```text
只判断投资相关文档类型。
只看输入中的 document_excerpt。
不要审查文档质量。
不要给投资建议。
输出 document_type、confidence、reason、missing_fields。
低置信度时给 unknown。
```

新增综合审查 prompt：

```text
src/investory/agent_core/prompts/tasks/investment_document_review_single_pass.md
```

要求：

```text
基于 document_text 和 review_framework 审查。
抽取事实时标注来自材料本身。
风险发现必须基于材料内容。
信息缺口要明确说明缺少什么。
不得给买入、卖出、持有、收益预测或个性化配置建议。
```

## 11. Gateway 计划

新增 schema：

```python
class InvestmentDocumentReviewRequest(BaseModel):
    payload: dict[str, Any]
    session_id: NonEmptyString | None = None
```

新增 route：

```text
POST /investment-document-review
```

新增 app state：

```python
INVESTMENT_DOCUMENT_REVIEW_FLOW_STATE_ATTR = "investment_document_review_flow"
```

不要复用 `/learning-entry`，因为文档审查是复合 flow，不是学习入口任务路由。

## 12. 测试计划

### 12.1 Rules 测试

覆盖：

```text
缺少 document_text -> missing input
明显买卖建议请求 -> refusal
实时价格/今天收益请求 -> refusal or missing capability
低置信度类型 -> unknown
每种 document_type 都能拿到 framework
```

### 12.2 Router 测试

使用 fake runner 验证：

```text
payload 被截断为 document excerpt
router prompt 被调用
结构化输出被转换为 route decision
低 confidence 降级为 unknown
```

### 12.3 Flow 测试

使用 fake router 和 fake reviewer 验证：

```text
缺少材料时不调用 LLM
拒绝投资建议时不调用审查模型
unknown 类型返回补充输入
known 类型生成最终 TaskResult
最终结果包含 document_type、review、boundary_notes
```

### 12.4 Gateway 测试

覆盖：

```text
POST /investment-document-review
session_id 透传
app.state 中可注入 fake flow
flow 异常按现有 gateway 错误风格返回
```

## 13. 分阶段实施顺序

### Phase 1: 合约与规则

新增：

```text
contracts/investment_document_review_state.py
runtime/flow/investment_document_review/document_review_rules.py
```

目标：

```text
定义 document type、state、route decision、review framework。
完成固定规则和 framework 单元测试。
```

### Phase 2: 路由器

新增：

```text
runtime/flow/investment_document_review/document_review_router.py
prompts/flows/investment_document_review_router.md
```

目标：

```text
复刻参考代码的 classify_document 思路。
只读取 document_text 前 N 个字符。
使用 RequestRunner 输出 Pydantic route decision。
```

### Phase 3: 单次综合审查

新增：

```text
task_models/investment_document_review.py
prompts/tasks/investment_document_review_single_pass.md
```

目标：

```text
按 document_type 注入 extract_focus 和 analyze_focus。
输出 extracted_facts、risk_findings、information_gaps、boundary_notes、summary。
```

### Phase 4: Flow 编排

新增：

```text
runtime/flow/investment_document_review/document_review_flow.py
```

目标：

```text
LangGraph 串起 policy gate、router、framework selection、single pass review、final result。
```

### Phase 5: API 接入

修改：

```text
src/investory/main.py
src/investory/gateway/api.py
src/investory/gateway/schemas.py
```

目标：

```text
新增 /investment-document-review。
支持 app.state 注入 flow。
补齐 gateway 测试。
```

## 14. 暂不做的事

v0 不做：

```text
TodoExecutionRunner 并发拆解
Plan 风险评估
Reflection 自检
多文档对比
YAML 动态配置加载
Agently 依赖引入
真实文件上传解析
外部实时市场数据查询
```

这些能力留给后续阶段，避免 v0 还没稳定就把编排复杂度拉满。

## 15. 验收标准

v0 完成时应满足：

1. 新 flow 与 `learning_entry` 完全分离。
2. `/investment-document-review` 可通过 payload 执行文档审查。
3. 缺少材料、低置信度、投资建议请求都有明确结果。
4. 已知投资文档类型能返回结构化审查结果。
5. 所有新增固定字符串都有 Enum 或模块级常量承载。
6. 相关测试通过：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_rules.py tests\test_investment_document_review_router.py tests\test_investment_document_review_flow.py tests\test_investment_document_review_gateway_api.py
```

