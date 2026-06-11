# Investory 参考 v2 加风险审批可借鉴点

## 背景

参考目录：

```text
C:\Users\hy120\Downloads\zhihullm\agent\lecture\08. 实战——智能文档审查助手\scripts\v2_加风险审批
```

该参考项目是一个教学版“文档审查 + 风险审批”流程。它的主流程大致是：

```text
route_subflow
  -> plan_gen_subflow
  -> dependency graph execution
  -> approval_flow
```

Investory 当前已经有更工程化的投资文档审查架构：

```text
policy gate
  -> classify document type
  -> build review framework
  -> generate todo plan / single-pass review
  -> execute todo plan
  -> build final result
```

因此，参考项目最值得借鉴的不是 Agently/TriggerFlow 的实现方式，而是它在审查完成后增加了一层“整体风险评估 + 审批处置决策”。

## 当前 Investory 已经覆盖的能力

Investory 已经吸收并强化了参考项目中的主要编排思想：

- 文档类型路由：已有 `InvestmentDocumentReviewLLMRouter`。
- 按文档类型选择审查框架：已有 `get_review_framework()`。
- To-Do plan 拆解：已有 `investment_document_review_plan` task。
- extract / analyze / synthesize 分工：已有独立 TaskSpec、Pydantic 输入输出模型和 prompt。
- DAG 执行：已有 `TodoExecutionRunner`，支持依赖分层、失败/跳过状态和重试策略。
- 长文档路径：已有 chunk extract fan-out、dimension analyze、synthesize 的结构。
- 可恢复执行：已有 `InvestmentDocumentReviewTodoResumeStore` 协议和 resume state 处理。
- 结构化结果：最终结果通过 `TaskResult` 和 `InvestmentDocumentReviewResult` 输出。

这些部分不需要照搬参考项目。

## 最值得借鉴的点

### 1. 增加整体风险评估阶段

参考项目的 `approval_flow` 会在所有 analyze 结果完成后，聚合分析发现并输出：

- `overall_risk`: `low` / `medium` / `high`
- `risk_reason`
- `critical_issues`
- `auto_proceed`

Investory 当前有 `risk_findings`，但这些只是报告内容的一部分，还缺少机器可读的整体风险等级。

建议新增独立模型，例如：

```python
class InvestmentDocumentReviewRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InvestmentDocumentReviewApprovalStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    HUMAN_APPROVED = "human_approved"
    CANCELLED = "cancelled"
```

这也符合仓库规则：固定业务字符串使用 `str, Enum`，不要散落 raw string。

### 2. 把“审查报告”和“是否放行”分开

当前 `build_final_result()` 主要输出：

```json
{
  "action": "complete",
  "document_type": "...",
  "route_reason": "...",
  "route_confidence": 0.95,
  "review": {}
}
```

可以借鉴参考项目，将最终结果扩展为：

```json
{
  "action": "complete",
  "document_type": "...",
  "route_reason": "...",
  "route_confidence": 0.95,
  "review": {},
  "risk_assessment": {
    "overall_risk": "high",
    "risk_reason": "...",
    "critical_issues": []
  },
  "approval": {
    "status": "pending_human_approval",
    "required_role": "compliance_reviewer"
  }
}
```

这样前端/API 可以明确区分：

- 报告是否已经生成。
- 文档整体风险等级是什么。
- 是否需要人工审批后才能放行。

### 3. 高风险进入人工审批状态

参考项目的处置策略是：

- low / medium：自动放行。
- high：等待人工确认。
- 人工拒绝：取消。

Investory 不应使用参考项目中的 `input()` 教学占位。更适合的方式是接入现有 `session_id` / resume 思路。

可考虑新增 LangGraph 节点：

```text
execute_review_todo_plan / run_single_pass_review
  -> assess_review_risk
  -> route_after_risk_assessment
      low/medium -> build_final_result
      high -> build_pending_approval_result
```

后续如果要接 webhook 或前端审批，可以再扩展为：

```text
pending_human_approval
  -> resume approval
  -> build_final_result / build_cancelled_result
```

### 4. 让风险审批只读审查结果，不重新自由审全文

参考项目的 `approval.py` 只收集 analyze task 的 findings，用这些发现做整体风险判断。

Investory 当前已经有 `_build_review_todo_summary()`，会确定性聚合：

- `extracted_facts`
- `risk_findings`
- `information_gaps`
- `boundary_notes`
- task status summaries

建议在它旁边增加类似 helper：

```python
def _build_review_risk_assessment_payload(...) -> dict[str, Any]:
    ...
```

输入建议只来自：

- analyze task 的 `risk_findings`
- failed / skipped task summary
- `information_gaps`
- `boundary_notes`
- `document_type`
- `route_confidence`

不建议让风险审批节点重新读取全文做自由判断。这样可以保持可审计性：风险等级来自已有审查证据，而不是第二次不受控的全文推理。

### 5. 新增独立 risk assessment task，而不是塞进 synthesize

当前 `investment_document_synthesize` 的职责是把 To-Do 结果合成为最终审查报告。

风险审批是另一类问题：它不是改写报告，而是根据报告和任务结果做处置分类。

建议新增：

```python
INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME = "investment_document_risk_assessment"
```

配套新增：

- `InvestmentDocumentReviewRiskAssessmentInput`
- `InvestmentDocumentReviewRiskAssessmentResult`
- `investment_document_risk_assessment.md`
- `INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK`

这样可以保持 task 边界清晰：

- `extract`：只提取事实。
- `analyze`：基于事实识别风险和缺口。
- `synthesize`：生成用户可读报告。
- `risk_assessment`：生成机器可读风险等级和审批建议。

## 不建议借鉴的点

- 不建议引入 Agently；Investory 已经统一在 LangGraph + TaskSpec + Pydantic 架构下。
- 不建议使用 `Literal["low", "medium", "high"]` 表达业务状态；应使用 `str, Enum`。
- 不建议用 `print` 表达流程日志；应使用 structured logging 和 `TaskResult`。
- 不建议用 `input()` 做人工审批；应使用 API 状态、session resume 或 webhook。
- 不建议自动剔除模型生成的不存在依赖；Investory 的 `ensure_valid_todo_plan()` 更适合生产，坏计划应明确失败。

## 建议实施优先级

1. 新增 risk assessment 输入输出模型和 prompt。
2. 新增 `investment_document_risk_assessment` TaskSpec。
3. 在 flow state 中加入 `risk_assessment` 和 `approval_status`。
4. 在 single-pass 和 To-Do synthesize 之后增加 `assess_review_risk` 节点。
5. low / medium 返回自动批准状态；high 返回 `pending_human_approval`。
6. 后续再接入人工审批 resume / webhook。

## 总结

参考项目的执行架构不需要照搬，Investory 当前实现已经更成熟。

真正值得吸收的是“审查完成后仍然需要一个可机器判断、可人工介入、可审计的风险审批层”。这会让投资文档审查从“生成报告”升级为“生成报告 + 给出明确处置状态”。
