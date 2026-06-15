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

## 这个例子里值得审查的风险

这里需要审查的重点，不是“这只基金本身的市场风险到底有多高”，而是“系统能不能把 AI 审查结果安全地转成可放行、可交付、可继续流转的状态”。

### 1. 高风险内容被自动放行

如果报告里已经出现重大披露缺口、费用异常、收益表述夸大、风险提示不足等发现，但最终仍只返回普通 `complete`，调用方可能会误以为这份结果已经可以直接使用。

因此，风险审批层首先要解决的是：哪些结果虽然“报告生成成功”，但实际上不能自动放行。

### 2. 审查报告和处置决策混在一起

当前 `risk_findings` 更像报告正文的一部分，适合给人读，但不适合直接驱动前端按钮、API 状态机或后续人工审核流。

如果没有单独的：

- `overall_risk`
- `approval_status`
- `required_role`

前端/API 很难稳定地区分：

- 报告是否已经生成。
- 风险等级是否已经明确。
- 当前结果是否还需要人工确认。

### 3. LLM 二次自由判断导致不可审计

如果风险审批节点重新读取全文，再做一次自由推理，它可能得出与 analyze / synthesize 阶段不同的结论。

这样会带来两个问题：

- 审批结论无法稳定追溯到前面的审查证据。
- 系统会出现“报告这么写，但审批状态却是另一套逻辑”的不一致。

因此，这一层更适合只消费结构化审查结果，例如：

- `risk_findings`
- `information_gaps`
- `boundary_notes`
- failed / skipped task summary

### 4. 任务失败或跳过被误当成低风险

在 To-Do DAG 路径里，部分 extract / analyze 任务可能失败、超时或被跳过，但 synthesize 仍然可能产出一份“看起来完整”的审查报告。

如果风险审批层忽略这些执行状态，系统就可能把“信息不完整”误判成“风险较低”。

因此，审批层不仅要看文档里发现了什么，也要看这份结论是不是建立在足够完整的执行结果之上。

### 5. 边界问题被包装成正常完成

例如用户实际上在请求：

- 买入 / 卖出建议
- 实时行情判断
- 收益预测
- 个性化投资决策

这些本应由 policy gate 拒绝或提前结束。如果结果层没有明确状态区分，调用方可能只看到“任务完成”，却看不到这其实是边界处理而不是正常审查通过。

### 6. 高风险缺少人工审批落点

high risk 不一定意味着立即失败，更合理的状态通常是：

- 审查已完成。
- 风险已识别。
- 当前不能自动放行。
- 需要人工审批后再决定是否继续。

这也是为什么 `pending_human_approval` 比单纯的 `complete` 或 `error` 更适合这个场景。它能把“已生成报告”和“尚未允许继续流转”这两个事实同时表达出来。

### 小结

因此，这个例子里“风险审批”的真正价值不是替代金融判断，而是补上一层系统级处置判断：

- 这份 AI 审查结果是否足够完整。
- 这份结果是否存在重大风险信号。
- 这份结果是否可以自动交付给下游。
- 还是必须先进入人工复核。

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

## Implementation steps

下面把上面的优先级展开为一轮可执行的实现顺序。这个实现顺序默认遵循当前 Investory 架构边界：

- 继续使用 `LangGraph + TaskSpec + Pydantic + TodoExecutionRunner`。
- 风险审批只消费审查结果，不重新自由审全文。
- 第一版先做“机器可读风险等级 + 待人工审批状态”，不在同一轮里引入完整审批 UI 或 webhook。

### 阶段 1：补齐风险评估合约与固定常量

目标：先把风险评估和审批状态表达成稳定合约，避免后续 flow、task、API 各自散落字符串。

Implementation steps:

1. 在投资文档审查相关 task model 模块中新增 `InvestmentDocumentReviewRiskLevel` 和 `InvestmentDocumentReviewApprovalStatus` 两个 `str, Enum`。
2. 新增 `InvestmentDocumentReviewRiskAssessmentInput`，输入字段至少包含：
   - `document_type`
   - `route_confidence`
   - `risk_findings`
   - `information_gaps`
   - `boundary_notes`
   - `task_status_summary`
3. 新增 `InvestmentDocumentReviewRiskAssessmentResult`，输出字段至少包含：
   - `overall_risk`
   - `risk_reason`
   - `critical_issues`
   - `approval_status`
   - `required_role`
   - `auto_proceed`
4. 用模块级常量固定 task name，例如：
   - `INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME`
   - 如有需要，再补 `COMPLIANCE_REVIEWER_ROLE`
5. 检查是否已有可复用的结果外壳；如果没有，再决定风险评估结果是挂在最终响应顶层，还是先挂在 `review.execution_trace` 旁路字段。

验收：

- Pydantic 模型能独立校验通过。
- 风险等级和审批状态不依赖 raw string。
- 结果字段足够支撑 flow 路由和前端展示。

### 阶段 2：新增独立 risk assessment task 与 prompt

目标：把“风险等级判断”从 `synthesize` 中拆开，形成职责单一的新 task。

Implementation steps:

1. 新增 `investment_document_risk_assessment` 对应的 TaskSpec 注册。
2. 新增 `investment_document_risk_assessment.md` prompt 文件。
3. 在 prompt 中明确约束：
   - 只能基于输入里的结构化审查证据判断。
   - 不得重新要求全文内容。
   - 不得输出投资建议、买卖建议或实时行情判断。
   - `high` 风险必须给出 `critical_issues`。
   - `low` / `medium` 默认 `auto_proceed=true`，`high` 默认 `auto_proceed=false`。
4. 明确 risk assessment task 的职责边界：
   - 不改写用户可读审查报告。
   - 不补造 extract / analyze 阶段没有产出的事实。
   - 只做聚合判断和处置建议。
5. 补最小单元测试，验证 TaskSpec 可被解析，且输出模型字段完整。

验收：

- `resolve_task_spec()` 能找到 `investment_document_risk_assessment`。
- prompt 和输出模型职责边界清晰，不与 `synthesize` 重叠。
- 风险评估 task 可以单独被调用并返回结构化结果。

### 阶段 3：在 flow 中插入 assess_review_risk 节点

目标：让 single-pass 和 To-Do 两条路径在生成审查报告后，都进入统一的风险评估节点。

Implementation steps:

1. 在 `InvestmentDocumentReviewState` 中新增：
   - `risk_assessment`
   - `approval_status`
   - 如有需要，再补 `approval_required_role`
2. 在 `document_review_flow.py` 中新增 `assess_review_risk` 节点，位置放在：
   - `run_single_pass_review` 之后，`build_final_result` 之前。
   - `synthesize_review_result` 之后，`build_final_result` 之前。
3. 在 `_build_review_todo_summary()` 附近新增 `_build_review_risk_assessment_payload()`，专门构造 risk assessment 输入。
4. 这个 payload 只聚合已有审查结果，建议包含：
   - `risk_findings`
   - `information_gaps`
   - `boundary_notes`
   - failed / skipped task summary
   - `document_type`
   - `route_confidence`
5. 不要在 `assess_review_risk` 节点重新读取 `document_text` 做自由判断；如果确实需要引用文本，也只传前面阶段已经抽取出的结构化证据。
6. 为 flow 增加条件路由，例如 `route_after_risk_assessment`：
   - `AUTO_APPROVED` -> `build_final_result`
   - `PENDING_HUMAN_APPROVAL` -> `build_pending_approval_result`
   - 后续如支持人工驳回，再扩展 `CANCELLED` 路径

验收：

- single-pass 和 To-Do 两条路径都能进入统一风险评估节点。
- 风险评估节点不重复审全文。
- flow 路由只依赖结构化状态，不依赖字符串散落判断。

### 阶段 4：把“审查结果”和“审批状态”分开输出

目标：保持用户可读报告不变，同时让 API 明确表达“是否需要人工审批”。

Implementation steps:

1. 扩展 `build_final_result()`，在现有 `review` 外增加：
   - `risk_assessment`
   - `approval`
2. 新增 `build_pending_approval_result()`，用于 high risk 场景返回：
   - 审查报告已经生成
   - 风险等级已经生成
   - 当前状态为 `pending_human_approval`
3. 明确第一版公开响应的最小字段集，例如：
   - `risk_assessment.overall_risk`
   - `risk_assessment.risk_reason`
   - `risk_assessment.critical_issues`
   - `approval.status`
   - `approval.required_role`
4. 保持现有 `review` 主结构尽量不变，避免把风险审批信息硬塞回 `InvestmentDocumentReviewResult` 的报告正文。
5. 如果担心 API 兼容性，第一版可先在内部结果和测试里落地，再决定是否在 gateway 响应顶层公开全部字段。

验收：

- 用户可读审查报告仍然存在。
- 高风险场景不会被误标成普通 `complete` 放行。
- 前端/API 可以直接判断是否需要人工审批。

### 阶段 5：为后续人工审批 resume 留好扩展点

目标：第一版先不实现完整人工审批闭环，但要把恢复接口和状态接缝留正确。

Implementation steps:

1. 在审批状态模型里保留：
   - `PENDING_HUMAN_APPROVAL`
   - `HUMAN_APPROVED`
   - `CANCELLED`
2. 设计好高风险中断后的最小恢复语义：
   - 审查任务已完成
   - 风险评估已完成
   - 仅审批决定待补充
3. 评估是否需要在 resume store 中新增审批相关字段，例如：
   - `approval_status`
   - `approval_decision_at`
   - `approval_actor_role`
4. 第一版即使不落库，也要在文档和 state 结构上明确：后续 resume 不应重新跑 extract / analyze / synthesize。
5. 如果后续接 webhook 或前端按钮，建议入口语义是“恢复审批决策”，不是“重新审查全文”。

验收：

- 高风险状态有明确的后续落点。
- 后续人工审批接入时，不需要推翻第一版 flow。
- 审批恢复和审查执行的职责边界清晰。

### 阶段 6：补齐测试、兼容性和执行记录

目标：让这一轮改动可验证、可回归、可审计。

Implementation steps:

1. 为 risk assessment model 和 task 增加单元测试。
2. 为 flow 增加路径测试，至少覆盖：
   - single-pass -> low/medium -> final result
   - To-Do synthesize -> low/medium -> final result
   - 任一路径 -> high -> pending approval result
3. 为 payload builder 增加测试，验证它只消费结构化审查结果，不依赖全文原文。
4. 为 gateway 或最终响应结构增加兼容性测试，确认：
   - 原有 `review` 字段未丢失
   - 新增 `risk_assessment` 和 `approval` 字段可选或按预期出现
5. 真正执行实施时，要同步更新对应 worklog，记录：
   - 修改点
   - 验证命令
   - 首次失败原因
   - 修复动作
   - 最终通过结果
6. 用仓库本地 `.venv` 跑 focused tests；如果这一轮未来进入实现，建议至少覆盖：

```powershell
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py
.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_gateway_api.py
```

验收：

- 风险评估新增能力有直接测试覆盖。
- 高风险审批路径不会破坏现有 API 主结构。
- worklog 能追溯实现、失败、修复和最终验证。

## 总结

参考项目的执行架构不需要照搬，Investory 当前实现已经更成熟。

真正值得吸收的是“审查完成后仍然需要一个可机器判断、可人工介入、可审计的风险审批层”。这会让投资文档审查从“生成报告”升级为“生成报告 + 给出明确处置状态”。
