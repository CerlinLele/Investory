# HYG File Upload 测试记录 — 模块拆分后完整流程验证

**会话 ID**: `apifox-hyg-file-upload`
**日期**: 2026-07-02
**目的**: 验证 `document_review_flow.py` 模块拆分（Step 4-5，节点逻辑迁移到 `document_review_nodes.py`）之后，`investment_document_review` 端到端流程（含 risk assessment + 人工审批路由）是否仍然正确。

## 代码版本

- 分支: `feature/2-2-structured-decision-routing-plan-reflection`
- 覆盖的相关提交:
  - `df61831` refactor: extract node handlers to separate module
  - `7d95566` refactor(flow): extract document review flow node handlers and slim core module
  - `1a06886` docs(worklog): record Step 4-5 completion
  - `93cca72` refactor(investment-document-review): implement runner factory compatibility adapter
  - `d3598c3` test: standardize hyg-file-upload test artifacts

## 产物

- `hyg-file-upload.log`（本次运行的完整日志）
- `hyg-file-upload-response.json`（API 原始响应）

## 结果概览

| 指标 | 值 |
|------|-----|
| `ok` | `true` |
| `document_type` | `etf_factsheet` |
| `route_confidence` | `0.99` |
| `chunk_count` / `task_count` | `25` / `29`（25 extract + 3 dimension analyze + 1 synthesize） |
| To-Do 执行 | `succeeded_count=29 failed_count=0 skipped_count=0 duration_ms=95521 synthesis_produced=true` |
| 反思 | `passed=true score=0.98 rounds=0 issue_count=0 safety_flag_count=2` |
| `risk_assessment.overall_risk` | `medium` |
| `risk_assessment.approval_status` | `pending_human_approval` |
| `risk_assessment.auto_proceed` | `false` |
| 最终 `action` | `pending_human_approval`（经 `route_after_risk_assessment` → `PENDING_APPROVAL_ROUTE` → `build_pending_approval_result`） |

## 时间分解（基于日志时间戳）

- Extract 阶段墙钟时间: 约 `58.2s`（25 个 chunk，3 槽并发流水线）
- Analyze 阶段墙钟时间: 约 `16.8s`（3 个并发维度任务：`analyze_risk_disclosures_completeness`、`analyze_historical_performance_boundary_statements`、`analyze_cost_impact_on_long_term_returns`）
- Synthesize 耗时: `20472 ms`
- To-Do 执行总耗时: `95521 ms`
- 反思阶段耗时: 约 `29.8s`
- Risk assessment + 审批路由: 约 `6.6s`
- 端到端总耗时（日志首行到末行）: 约 `131.9s`

## 为什么 `overall_risk=medium` 但仍 `pending_human_approval`

- `risk_assessment.critical_issues` 列出 3 项：披露文本被截断、追踪方法说明缺失、完整表现图表未见。
- Prompt（`investment_document_risk_assessment.md`）中 `auto_proceed=true` 只是 medium 风险的**默认建议**，并没有硬性约束"何时可以覆盖默认值"，模型基于 `critical_issues` 非空自行选择覆盖为 `pending_human_approval` / `auto_proceed=false`。
- 代码层（`InvestmentDocumentReviewRiskAssessmentResult`，见 `task_models/investment_document_review.py`）目前没有 `model_validator` 校验 `overall_risk`、`critical_issues`、`approval_status`、`auto_proceed` 四个字段之间的一致性，完全依赖 LLM 自洽输出。

## 与既往运行的回归对比

- 任务结构（29 = 25 extract + 3 analyze + 1 synthesize）与 `2026-07-01-1.analyze-concurrency` 一致，说明模块拆分（`flow.xxx()` → `flow.nodes.xxx()`）未改变 To-Do 计划生成行为。
- Extract/Analyze 并发模式未变：3 槶 extract 流水线、3 个 analyze 维度同时启动。
- 本次运行首次在 `test-results/hyg-file-upload/` 下完整跑通并留存了 risk assessment + 人工审批路由到 `pending_human_approval` 的结果（`2026-06-10` 与 `2026-07-01` 的记录只覆盖并发性验证，未涉及审批阶段）。

## Chunk 截断问题分析

### 问题现象

`critical_issues` 中反复出现"Several disclosure sentences are truncated"。这看起来像"整段塞进去 vs 分块"的矛盾：
- 分块太小 → 会有截断（当前表现）
- 整段塞进去 → 避免截断，但长文档会顶到上下文窗口上限

### 根本原因

**不是矛盾，而是当前分块参数偏保守**：

- [document_chunker.py:7-8](src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py#L7-L8) 设置 `CHUNK_SIZE=500` 字符、`CHUNK_OVERLAP=50` 字符
- 一个 500 字符的 chunk ≈ 80-100 个英文单词；50 字符的 overlap 只占 chunk 大小的 10%
- ETF factsheet 里的风险披露、免责条款、费用说明等关键句子通常超过 500 字符
- 当句子跨越两个 chunk 的边界时，50 字符 overlap 往往不足以将整句完整放入任何一个 chunk
- 结果：某个 chunk 的 extract 任务只看到"Investing involves risk, including possible loss of"但看不到后半句，被标记为 truncated

### 改进方案

三种思路可单独或组合使用（都只需参数/payload 调整，无架构改动）：

**方案 1：增加 overlap 比例**
- 当前：`CHUNK_OVERLAP=50`（10% of chunk size）
- 改进：`CHUNK_OVERLAP=75-100`（15-20% of chunk size）
- 效果：让跨界句子更可能在至少一个 chunk 里完整出现
- 代价：chunk 间重复内容增多，per-chunk extract 的去重成本略增

**方案 2：扩大 chunk_size**
- 当前：`CHUNK_SIZE=500`
- 改进：`CHUNK_SIZE=1000-1500`
- 效果：chunk 总数减少（从 25 降到 10-15），边界数量随之减少
- 代价：单次 extract 调用的 token 成本略增，但总调用次数反而减少，可能抵偿

**方案 3：邻近上下文传递**
- 在每个 chunk 的 extract payload 中额外带上前一 chunk 末尾 + 后一 chunk 开头的小段原文（作为"引用上下文"）
- 这些上下文不参与该 chunk 的评分，仅用于帮助识别跨界句子是否完整
- 效果：即使 chunk_size 不变，也能显著降低"半句话"问题
- 代价：payload 构造逻辑稍复杂，但无额外 LLM 调用

### 当前状态

本次运行的 3 项 `critical_issues` 中 2 项与截断有关，说明这个问题已经被 LLM 检测到且列为"阻止自动通过"的信号。如果后续要降低截断概率，方案 1+2 的组合（overlap 调到 15-20% + chunk_size 到 1000）可以先试，成本最低。

---

## Performance Chart Gap 问题分析

### 问题现象

`critical_issues` 的第三项和 `information_gaps` 中出现：
- "The exact full performance chart or hypothetical $10,000 path is not visible."
- "The full performance chart and some performance-context details are not visible."

这不是分块截断问题，而是根本上的**模态限制**。

### 根本原因

[pdf_extractor.py:26-29](src/investory/gateway/pdf_extractor.py#L26-L29) 中 PDF 提取仅使用 `page.extract_text()`，只能从 PDF 的文字层中提取内容。ETF factsheet 里的"Growth of $10,000"图表通常是**矢量图形或栅格图像**（曲线、坐标轴等），不是可提取的文本，因此无论如何细化分块都无法捕获这条曲线的数据——这不是切割问题，而是内容本身的模态不匹配。

### 信息冗余性分析

但这个 gap 是否真的代表审查**缺失了关键数据**？对比本次结果已提取的数据（[response.json:19](test-results/hyg-file-upload/2026-07-02/hyg-file-upload-response.json#L19)）：

> "Calendar-year performance is shown for 2021 to 2025, and annualized performance is shown for NAV, market price, and benchmark across 1-year, 3-year, 5-year, 10-year, and since inception periods."

同样的收益数据**已经以文字和表格形式完整提取**。那条"$10,000 增长曲线图"只是把这些数字换成图形展示的冗余表达，并不包含额外的数据维度。也就是说，这个 information_gap 本质上是"图表的**视觉呈现方式**没被捕获"，而不是"审查缺失了关键的收益/风险数据"。

### 为什么这个 Gap 被列为阻止自动通过的信号

当前 `investment_document_extract.md` 和 `investment_document_synthesize.md` 的 prompt 没有区分两类 gap：
1. **真实数据缺失**：披露文本被截断、关键风险说明缺失、费用详情不完整
2. **视觉冗余缺失**：图表没被提取，但相同的数据已经以文字形式提供

这导致两类 gap 混合计入 `information_gaps`/`critical_issues`，被同等加权，拉高了风险判定，不必要地触发了人工审批。

### 改进建议

无需引入图像识别或多模态 LLM（投入成本高，信息收益低）。而是在 extract prompt 中加入一条规则，明确区分两类 gap。

修改 [investment_document_extract.md](src/investory/agent_core/prompts/tasks/investment_document_extract.md) 的 Requirements 部分，加入：

> **Visual-only redundancy rule**: If a graphical element (e.g., a performance growth chart, pie chart, or diagram) presents the same quantitative data that is otherwise available in extracted text, tables, or structured fields, note it under `boundary_notes` as "visual-only representation" rather than `information_gaps`. Example: "The $10,000 growth chart visualizes the same annual returns data already captured in the performance table; chart rendering details are not captured by text extraction."

这样做的效果：
- Extract 任务会将图表缺失归类到 `boundary_notes`（源限制说明），而不是 `information_gaps`（内容缺失）
- Synthesize 任务会在最终 review 的 `boundary_notes` 里带上这条说明
- Risk assessment 不会因为"视觉冗余"而升高风险等级

### 预期影响

若实施此改进，本次运行的 `critical_issues` 会从 3 项降到 2 项（仅保留真实的截断问题），很可能将 `approval_status` 从 `pending_human_approval` 改判为 `auto_approved`，因为剩下的 2 项截断都是 Chunk 参数问题引起的（可独立优化）。

---

## 后续建议

### 1. Risk Assessment 的一致性校验

- 如果 `medium` 风险落到 `pending_human_approval` 的情况后续造成下游困惑，可考虑：
  - 在 prompt 中明确"覆盖默认 `auto_proceed`"的触发条件（例如仅当 `critical_issues` 非空时才允许覆盖）；或
  - 在 `InvestmentDocumentReviewRiskAssessmentResult` 上加 `model_validator`，强制 `critical_issues` 非空 ⟺ `approval_status != auto_approved`。

### 2. Chunk 截断优化

- 调整 `CHUNK_SIZE` 和 `CHUNK_OVERLAP` 参数，目标：`CHUNK_SIZE=1000, CHUNK_OVERLAP=150-200`
- 可选：实现邻近上下文传递（方案 3），进一步降低边界截断

### 3. 测试制品完整性

- 本次运行尚未生成 `hyg-file-upload-test-result.md` / `hyg-file-upload-execution-diagram.html`，如需完整书面报告可后补。
