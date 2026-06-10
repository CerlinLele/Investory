# Investory 投资文档审查助手独立 Flow 设计建议

## 1. 结论

可以新开一个独立 flow 来做“智能文档审查助手”，而且这比把能力塞进现有 `learning_entry_flow.py` 更干净。

现有 `learning_entry_flow.py` 更像学习入口：

```text
用户输入
  -> 判断 QA / summary / instrument brief
  -> 执行单个学习型任务
```

投资场景下的“智能文档审查助手”是另一类业务 flow：

```text
文档输入
  -> 文档类型识别
  -> 多维度抽取
  -> 风险审查
  -> 报告生成
  -> Reflection 验收
```

因此建议新增独立 flow：

```text
src/investory/agent_core/runtime/flow/investment_document_review_flow.py
```

对应能力名称：

```text
investment_document_review
```

## 2. 为什么应该独立成 Flow

### 2.1 业务边界不同

`learning_entry_flow.py` 的核心问题是：

```text
用户想做哪种学习任务？
```

投资文档审查 flow 的核心问题是：

```text
这份投资相关文档是什么类型？
应该审查哪些维度？
哪些风险和限制需要明确指出？
最终报告是否安全、完整、可解释？
```

这两个问题虽然都在投资学习语境下，但业务主线不同。

### 2.2 状态结构不同

学习入口通常只需要：

```text
candidate_task_type
resolved_task_name
task_payload
output
```

文档审查需要更多中间状态：

```text
document_type
review_plan
extraction_results
risk_findings
draft_report
reflection_result
final_report
```

如果把这些字段塞进 `LearningEntryState`，会让学习入口状态膨胀，也会模糊 flow 的职责。

### 2.3 执行模式不同

学习入口当前更适合单任务执行：

```text
TaskSpec + payload
  -> TaskExecutor
  -> TaskExecutionPipeline
```

文档审查天然更像复合任务：

```text
classify document type
  -> build review checklist / todo plan
  -> execute multiple extraction tasks
  -> synthesize report
  -> reflection review
```

因此它更适合接入 `TodoExecutionRunner`、Plan 和 Reflection。

## 3. 推荐命名

### 3.1 Flow 文件

```text
src/investory/agent_core/runtime/flow/investment_document_review_flow.py
```

### 3.2 State 合约

```text
src/investory/agent_core/contracts/investment_document_review_state.py
```

### 3.3 文档类型路由

```text
src/investory/agent_core/runtime/flow/investment_document_review_router.py
```

### 3.4 Prompt

```text
src/investory/agent_core/prompts/flows/investment_document_review_router.md
src/investory/agent_core/prompts/tasks/investment_document_review_report.md
```

### 3.5 API 路径

推荐使用业务明确的路径：

```text
/investment-document-review
```

也可以使用更通用的：

```text
/document-review
```

但当前项目是 Investory，建议优先使用 `investment_document_review`，避免后续和通用文档审查混淆。

## 4. 推荐 Flow 链路

建议第一版链路：

```text
InvestmentDocumentReviewFlow

input document/material
  -> InvestoryPolicyGate
  -> classify_document_type
  -> build_review_plan
  -> execute_review_tasks
  -> synthesize_review_report
  -> optional_reflection
  -> build_final_result
```

对应 LangGraph 节点可以是：

```text
EVALUATE_POLICY_GATE
CLASSIFY_DOCUMENT_TYPE
BUILD_REVIEW_PLAN
EXECUTE_REVIEW_TASKS
SYNTHESIZE_REVIEW_REPORT
RUN_REFLECTION
BUILD_FINAL_RESULT
BUILD_REFUSAL_RESULT
BUILD_MISSING_INPUT_RESULT
```

第一版可以先不实现所有节点，先保留清晰边界。

## 5. 推荐 State 结构

建议新增独立 state，而不是复用 `LearningEntryState`。

示例结构：

```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InvestmentDocumentType(str, Enum):
    ETF_FACTSHEET = "etf_factsheet"
    FUND_PROSPECTUS = "fund_prospectus"
    PRODUCT_BROCHURE = "product_brochure"
    EARNINGS_REPORT = "earnings_report"
    LEARNING_MATERIAL = "learning_material"
    UNKNOWN = "unknown"


class InvestmentDocumentReviewState(BaseModel):
    session_id: str
    input_payload: dict[str, Any]
    document_type: InvestmentDocumentType | None = None
    review_plan: dict[str, Any] | None = None
    task_results: list[dict[str, Any]] = Field(default_factory=list)
    risk_findings: list[dict[str, Any]] = Field(default_factory=list)
    draft_report: dict[str, Any] | None = None
    reflection_result: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
```

后续正式实现时，可以把 `review_plan`、`risk_findings`、`draft_report` 替换为更严格的 Pydantic 模型。

## 6. 文档类型建议

第一版可以支持以下文档类型：

```text
etf_factsheet
fund_prospectus
product_brochure
earnings_report
learning_material
unknown
```

每种类型对应不同审查重点：

| 文档类型 | 审查重点 |
|---|---|
| `etf_factsheet` | 标的指数、费用、资产配置、风险、历史表现说明边界 |
| `fund_prospectus` | 投资范围、费用、风险因素、限制条款、赎回规则 |
| `product_brochure` | 产品结构、收益表述、风险揭示、适用条件、限制说明 |
| `earnings_report` | 收入、利润、现金流、风险提示、不能外推的结论 |
| `learning_material` | 概念、机制、关键术语、学习重点、材料内外事实边界 |
| `unknown` | 要求用户补充文档类型或材料上下文 |

## 7. 投资文档审查的业务边界

这个 flow 的“审查”必须保持学习和信息整理边界。

可以做：

```text
事实抽取
费用结构整理
风险因素识别
限制条款说明
信息缺口标记
材料内外事实区分
学习型报告生成
```

不应该做：

```text
买入建议
卖出建议
持仓建议
收益承诺
价格预测
个性化资产配置建议
绕过实时数据能力限制的判断
```

这意味着新 flow 仍然应该复用 `InvestoryPolicyGate`，而不是绕过现有安全边界。

## 8. 和现有组件的关系

### 8.1 复用 InvestoryPolicyGate

投资文档审查仍然需要前置策略门：

```text
缺少文档内容 -> ask_for_missing_input
投资建议请求 -> refuse_and_redirect
实时数据请求但不支持 -> refuse_and_redirect
需要用户确认 -> ask_for_missing_input / confirmation_required
```

### 8.2 复用 TaskExecutor

单个审查步骤可以继续由 `TaskExecutor` 执行：

```text
extract_fees
extract_risks
extract_constraints
synthesize_report
```

不建议把单任务执行逻辑复制到新 flow。

### 8.3 复用 TodoExecutionRunner

文档审查天然适合 `TodoExecutionRunner`：

```text
t1: extract_basic_info
t2: extract_fee_structure
t3: extract_risk_factors
t4: extract_constraints
t5: synthesize_report, depends_on=[t1,t2,t3,t4]
```

其中 `t1` 到 `t4` 可以并发，`t5` 必须等待前置任务。

### 8.4 后续复用 Reflection

Reflection 不应该替代 Policy Gate，而应该作为输出验收层：

```text
synthesize_report
  -> reflection checks completeness / safety / factual boundaries
  -> final_report
```

## 9. 不建议的设计

### 9.1 不建议塞进 learning_entry_flow.py

原因：

```text
learning_entry_flow.py 已经承担学习入口路由。
文档审查需要独立的 document_type、review_plan、risk_findings、reflection_result。
强行复用会让状态和条件分支变复杂。
```

### 9.2 不建议改造 TaskExecutionPipeline

`TaskExecutionPipeline` 当前边界很清楚：

```text
validate input
  -> build prompt
  -> call model
  -> validate output
  -> build result
```

文档审查是 flow 编排，不是单个 TaskSpec 的执行细节。

### 9.3 不建议一开始就做全动态 LLM Todo

第一版可以先使用固定 checklist。

原因：

```text
固定 checklist 更容易测试。
文档类型有限。
风险边界更可控。
后续再让 LLM 动态生成 todo plan。
```

## 10. 最小可行版本

建议 MVP 只做四步：

```text
1. 新增 InvestmentDocumentReviewState 和 DocumentReviewResult。
2. 新增 document type router。
3. 根据 document_type 使用固定 review checklist。
4. 生成最终审查报告。
```

第一版可以暂时不接：

```text
TodoExecutionRunner
PlanPolicyGate
ReflectionRunner
复杂多文档并发
```

等 MVP 跑通后，再分阶段增强。

## 11. 推荐演进路线

### Phase 1：独立 flow 骨架

目标：

```text
新增 investment_document_review_flow.py
新增独立 State
新增固定文档类型枚举
新增基础 API 路径
```

### Phase 2：固定 checklist 审查

目标：

```text
根据 document_type 选择审查维度
输出结构化审查报告
覆盖费用、风险、限制、信息缺口
```

### Phase 3：接入 TodoExecutionRunner

目标：

```text
多个审查维度并发执行
支持 depends_on
支持失败策略
```

### Phase 4：接入 Reflection

目标：

```text
检查报告完整性
检查是否越界成投资建议
检查是否伪造实时数据
检查是否区分材料内事实和外部推断
```

### Phase 5：支持多文档和横向比较

目标：

```text
多份 ETF factsheet 对比
多只基金说明书对比
产品材料风险差异对比
```

## 12. 推荐最终架构

长期看，Investory 可以形成两个并列入口：

```text
learning_entry_flow.py
  -> 面向学习型单任务
  -> QA / summary / instrument brief

investment_document_review_flow.py
  -> 面向文档审查型复合任务
  -> document type routing / checklist / todo / report / reflection
```

共享底层能力：

```text
InvestoryPolicyGate
TaskExecutor
RequestRunner
TodoExecutionRunner
ToolRegistry
ReflectionRunner
```

这样既能保持现有学习入口简单，也能给投资文档审查助手留下完整的演进空间。

## 13. 总结

新开 flow 是合理的。

原因：

```text
业务目标不同
状态结构不同
执行模式不同
风险边界更复杂
后续更适合接入 Todo / Plan / Reflection
```

推荐方向：

```text
不要把投资文档审查塞进 learning_entry_flow.py。
新增 investment_document_review_flow.py。
复用现有 Policy Gate、TaskExecutor 和 Todo runner。
先做固定 checklist MVP，再演进到完整全链路审查助手。
```
