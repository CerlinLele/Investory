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

## 后续建议

- 如果 `medium` 风险落到 `pending_human_approval` 的情况后续造成下游困惑，可考虑：
  - 在 prompt 中明确"覆盖默认 `auto_proceed`"的触发条件（例如仅当 `critical_issues` 非空时才允许覆盖）；或
  - 在 `InvestmentDocumentReviewRiskAssessmentResult` 上加 `model_validator`，强制 `critical_issues` 非空 ⟺ `approval_status != auto_approved`。
- 本次运行尚未生成 `hyg-file-upload-test-result.md` / `hyg-file-upload-execution-diagram.html`，如需完整书面报告可后补。
