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

字段语义建议（v0）：

```text
document_type_hint：
- 含义：用户提供的“文档类型提示”，用于辅助路由，不替代路由判断。
- 示例：etf_factsheet / fund_prospectus / product_brochure / earnings_report / learning_material。
- 处理原则：当 hint 与文档内容冲突时，以文档内容为主，并在 route reason 说明。

review_goal：
- 含义：用户希望本次审查重点关注的方向。
- 合法示例：检查费用与风险披露、提取关键事实、识别信息缺口、总结学习重点。
- 非法示例：是否现在买入、给我仓位建议、预测今天/下周收益。
- 处理原则：review_goal 仅影响审查关注点，不得改变投资边界。
```

### 6.2 路由输出

```python
class InvestmentDocumentReviewRouteDecision(BaseModel):
    document_type: InvestmentDocumentType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
```

`missing_fields` 在 v0 建议区分两类语义：

```text
硬性缺失（阻塞执行）：
- 仅 `document_text`。没有材料时直接要求补充。

补充信息（用于提升路由/审查质量）：
- 低置信度或 `unknown` 时，优先要求 `document_type_hint`。
- `review_goal` 作为可选补充信息，不作为默认阻塞字段。
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
2.1 中期（实现细化）：把 payload 文本拼接与字段判空辅助函数沉淀到共享模块（如 `runtime/flow/common/payload_rules.py`），两侧规则文件通过导入复用，避免 `_has_value`、`_as_text`、拼接逻辑重复。
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

### 13.1 具体 Implementation Steps

下面的步骤按可独立验证、可逐步提交的顺序排列。每一步都尽量限制改动面，避免在 v0 阶段同时引入 Todo、Plan、Reflection 或共享 policy 大重构。

#### Step 1: 建立文档审查合约

目标文件：

```text
src/investory/agent_core/contracts/investment_document_review_state.py
```

实现内容：

1. 定义输入字段常量：`DOCUMENT_TEXT_FIELD`、`DOCUMENT_TYPE_HINT_FIELD`、`REVIEW_GOAL_FIELD`。
2. 定义 `InvestmentDocumentType(str, Enum)`，包含 `etf_factsheet`、`fund_prospectus`、`product_brochure`、`earnings_report`、`learning_material`、`unknown`。
3. 定义 `InvestmentDocumentReviewRouteDecision`，字段为 `document_type`、`confidence`、`reason`、`missing_fields`。
4. 定义 `DocumentReviewFramework`，字段为 `extract_focus`、`analyze_focus`。
5. 定义 `InvestmentDocumentReviewState`，字段覆盖 `session_id`、`input_payload`、`missing_fields`、`document_type`、`route_reason`、`route_confidence`、`review_framework`、`review_payload`、`output`。

注意事项：

```text
固定字符串必须落在 Enum 或模块级常量里。
state 中暂时不要放 Todo/Plan/Reflection 字段，避免 v0 过早膨胀。
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_rules.py
```

这一阶段可以先让测试文件只验证 enum、state 默认值和 Pydantic 校验。

#### Step 2: 增加文档审查规则与框架

目标文件：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py
tests/test_investment_document_review_rules.py
```

实现内容：

1. 定义 `DOCUMENT_ROUTER_MAX_CHARS = 600`，对齐参考代码只看文档开头的思路。
2. 定义 `DEFAULT_DOCUMENT_ROUTE_CONFIDENCE_THRESHOLD = 0.6`。
3. 定义 `UNKNOWN_DOCUMENT_MISSING_FIELDS = [DOCUMENT_TYPE_HINT_FIELD]`，用于低置信度或无法判断类型时要求补充信息。
4. 实现 `detect_missing_fields(payload)`，v0 仅检查 `document_text` 这一硬性必填项。
5. 实现 `looks_like_investment_advice(payload)`，主要检测 `review_goal` / `document_type_hint` 等用户意图字段中的明显买入、卖出、持有、择时、资产配置建议请求；不要仅因 `document_text` 出现相关词汇而拒绝。
6. 实现 `requires_realtime_data(payload)`，主要检测 `review_goal` / `document_type_hint` 等用户意图字段中的今天价格、实时收益、最新涨跌、短期预测请求；不要把文档正文中的历史或日期描述误判为实时请求。
7. 实现 `build_document_excerpt(payload)`，只取 `document_text` 前 `DOCUMENT_ROUTER_MAX_CHARS` 个字符。
8. 定义 `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE`，为每个已知 `InvestmentDocumentType` 提供 `DocumentReviewFramework`。
9. 实现 `get_review_framework(document_type)`，对 `unknown` 返回 `None` 或抛出明确错误，避免误审查。
10. 可选复用优化：抽取 `has_value` / `as_text` / `join_text_fields` 等 payload 处理辅助函数到共享模块（例如 `runtime/flow/common/payload_rules.py`），供 `document_review_rules` 与 `learning_entry_rules` 共同使用，避免重复实现。

测试覆盖：

```text
missing document_text -> 返回 document_text
完整 document_text -> 无 missing fields
unknown / 低置信度 -> missing_fields 包含 document_type_hint
买卖建议请求 -> looks_like_investment_advice 为 True
实时价格请求 -> requires_realtime_data 为 True
document_text 含 buy/sell 等术语但用户未提出建议请求 -> 不触发 advice 拦截
document_text 含 latest/quarter/date 等历史描述但用户未请求实时数据 -> 不触发 realtime 拦截
document excerpt 被截断到 600 字符
每个已知 document_type 都能取到 framework
unknown 不进入正式 framework
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_rules.py
```

#### Step 3: 实现 LLM 文档类型路由器

目标文件：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py
src/investory/agent_core/prompts/flows/investment_document_review_router.md
tests/test_investment_document_review_router.py
```

实现内容：

1. 定义 `InvestmentDocumentReviewRouter(Protocol)`，方法为 `route(payload) -> InvestmentDocumentReviewRouteDecision`。
2. 定义 `InvestmentDocumentReviewLLMRouter`，构造参数支持注入 `RequestRunner`。
3. 在 `route()` 中调用 `build_document_excerpt(payload)`，只把 `document_excerpt`、`document_type_hint`、`review_goal` 传给 prompt。
4. 使用 `load_prompt_text("base", "system.md")`、`common_rules.md`、`input_data_block.md` 和新的 router prompt。
5. 使用 `self.runner.run(messages, InvestmentDocumentReviewRouteDecision)` 获取结构化结果。
6. 增加 `normalize_route_decision(decision)`，当 `confidence < DEFAULT_DOCUMENT_ROUTE_CONFIDENCE_THRESHOLD` 时将 `document_type` 降级为 `unknown`，并保留 `reason`。

Prompt 要求：

```text
只判断投资相关文档类型。
只基于 document_excerpt 与 hint。
不要审查质量。
不要输出投资建议。
无法判断或低置信度时使用 unknown。
```

测试覆盖：

```text
fake runner 收到的是 document_excerpt，不是全文
document_type_hint 能进入输入块
runner 返回 known type 时原样返回
runner 返回低 confidence 时降级 unknown
missing_fields 能保留
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_router.py
```

#### Step 4: 建立单次综合审查 task model

目标文件：

```text
src/investory/agent_core/task_models/investment_document_review.py
src/investory/agent_core/prompts/tasks/investment_document_review_single_pass.md
```

实现内容：

1. 定义 `InvestmentDocumentReviewInput`，字段为 `document_text`、`document_type`、`extract_focus`、`analyze_focus`、可选 `review_goal`。
2. 定义 `InvestmentDocumentReviewResult`，字段为 `document_type`、`extracted_facts`、`risk_findings`、`information_gaps`、`boundary_notes`、`summary`、可选 `learning_next_steps`。
3. 在 prompt 中强调所有结论必须来自材料或明确标为信息缺口。
4. 删除或避免 `suggestions` 字段，避免输出滑向投资建议。
5. 明确禁止买入、卖出、持有、收益预测、个性化配置建议。

暂时不做：

```text
不注册到 TASKS，先让新 flow 内部通过 TaskSpec 或直接 TaskExecutor 使用。
不接 TodoExecutionRunner。
```

验证方式：

```text
.venv\Scripts\python.exe -m pytest tests/test_task_models.py
```

如果当前没有覆盖 task model 的专门测试，可以在后续 Step 6 的 flow 测试里通过 fake executor 覆盖 payload 结构。

#### Step 5: 注册单次审查任务规格

目标文件：

```text
src/investory/agent_core/tasks.py
tests/test_gateway_routing.py 或现有 routing 相关测试
```

实现内容：

1. 增加模块级常量 `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME = "investment_document_review_single_pass"`。
2. 增加 `INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK = TaskSpec(...)`。
3. 将任务加入 `TASKS`。
4. 如果不希望 `/tasks` 暴露该底层 task，可以先不注册到 gateway routing，而是在 flow 内部直接引用常量 task spec。二者选一种，不要同时模糊处理。

推荐选择：

```text
v0 先注册到 TASKS，便于复用 TaskExecutor 和测试。
业务入口仍然只暴露 /investment-document-review。
```

测试覆盖：

```text
resolve_task_spec("investment_document_review_single_pass") 能返回 TaskSpec
TaskSpec.prompt_name 指向 investment_document_review_single_pass
input_model/output_model 为文档审查模型
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests
```

#### Step 6: 实现文档审查 Flow

目标文件：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py
tests/test_investment_document_review_flow.py
```

实现内容：

1. 定义 `INVESTMENT_DOCUMENT_REVIEW_TASK_NAME = "investment_document_review"`。
2. 定义结果字段常量：`ACTION_FIELD`、`MESSAGE_FIELD`、`DOCUMENT_TYPE_FIELD`、`REVIEW_FIELD`、`MISSING_FIELDS_FIELD`。
3. 定义 `InvestmentDocumentReviewNode(str, Enum)`，覆盖 policy、router、framework、review、final、missing、refusal 节点。
4. `run(payload, session_id=None)` 创建 `InvestmentDocumentReviewState`，调用 LangGraph，返回 `TaskResult`。
5. `evaluate_policy_gate()` 先用本 flow 的轻量规则处理 missing/advice/realtime，暂不强行复用 learning entry 的 `InvestoryPolicyGate`。
6. `classify_document_type()` 调用 `InvestmentDocumentReviewRouter`。
7. `route_after_classification()` 在 `unknown` 或低置信度时走 missing result。
8. `build_review_framework()` 从 `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE` 取 framework，构造 `review_payload`。
9. `run_single_pass_review()` 调用 `TaskExecutor.run(INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK, review_payload)`。
10. `build_final_result()` 包装为 `TaskResult(ok=True, task_name=INVESTMENT_DOCUMENT_REVIEW_TASK_NAME, result=...)`。
11. `build_investment_document_review_flow()` 支持注入 fake executor、fake router、runner，保持测试友好。

测试覆盖：

```text
missing document_text -> 返回 ask_for_missing_input，router/executor 不被调用
投资建议请求 -> 返回 refuse_and_redirect，router/executor 不被调用
实时价格请求 -> 返回 refuse_and_redirect 或 missing capability，router/executor 不被调用
router 返回 unknown -> 返回 ask_for_missing_input，executor 不被调用
router 返回 known type -> 选择 framework 并调用 executor
executor 返回 TaskResult error -> flow 保留下游错误
成功路径 -> 输出 document_type、review、route_reason、route_confidence
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py
```

#### Step 7: 接入 Gateway schema 与 API

目标文件：

```text
src/investory/gateway/schemas.py
src/investory/gateway/api.py
src/investory/main.py
tests/test_investment_document_review_gateway_api.py
```

实现内容：

1. 在 `schemas.py` 增加 `InvestmentDocumentReviewRequest`，结构与 `LearningEntryRequest` 保持一致。
2. 在 `api.py` 增加 `INVESTMENT_DOCUMENT_REVIEW_FLOW_STATE_ATTR` 和 `INVESTMENT_DOCUMENT_REVIEW_ROUTE = "/investment-document-review"`。
3. 增加 `execute_investment_document_review_request()`，处理 `session_id`、flow 注入和 `_to_gateway_response()`。
4. 增加 `@router.post(INVESTMENT_DOCUMENT_REVIEW_ROUTE, response_model=TaskResponse)`。
5. 在 `main.py` 的 `create_app()` 里初始化并挂载 `build_investment_document_review_flow()`。
6. 保持 `/learning-entry` 不变，不复用 learning entry request model。

测试覆盖：

```text
POST /investment-document-review 返回 TaskResponse
session_id 能透传
app.state fake flow 能被使用
flow 返回 error result 时 gateway 正确转换
learning-entry 原有 gateway tests 不受影响
```

验证：

```text
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_gateway_api.py tests\test_learning_entry_gateway_api.py
```

#### Step 8: 做一次全量回归与导入检查

目标：

```text
确认新增 flow 没有破坏 learning_entry、gateway、task execution 和 todo_core。
```

命令：

```text
.venv\Scripts\python.exe -m pytest
```

额外检查：

```text
rg "runtime\.flow\.learning_entry_router|runtime\.flow\.learning_entry_flow" src tests
rg "investment_document_review" src tests docs
git status --short
git diff --stat
```

验收：

```text
测试全绿。
旧 learning_entry import 路径没有回退到扁平 flow。
新增文件都位于 investment_document_review 子包内。
未把 Agently 引入依赖。
```

#### Step 9: 建议提交拆分

建议按下面粒度提交，便于回滚和 review：

1. `feat(document-review): add review contracts and rules`
2. `feat(document-review): add document type router`
3. `feat(document-review): add single pass review task`
4. `feat(document-review): add review flow orchestration`
5. `feat(api): expose investment document review endpoint`

如果希望先保持更小变更，也可以把 Step 1 和 Step 2 合并为一个提交，但不要把 API 接入和底层合约混在同一个提交里。

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
