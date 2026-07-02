# 投资文档审查 Chunk 截断与 Visual Gap 改进计划

## 背景

来源：[test-results/hyg-file-upload/2026-07-02/hyg-file-upload-notes.md](../../../test-results/hyg-file-upload/2026-07-02/hyg-file-upload-notes.md)

`2026-07-02` 这次 `hyg-file-upload` apifox 回归测试中，`investment_document_review` 端到端流程本身正确（模块拆分后行为未变），但结果落在 `risk_assessment.approval_status=pending_human_approval`，`critical_issues` 有 3 项：

1. 披露文本被截断（2 项，均由 chunk 边界切断长句引起）
2. 完整表现图表（`$10,000` 增长曲线）未被提取（1 项，属于模态限制，不是内容缺失）

笔记中的分析已经定位了根因和具体改法，但"后续建议"小节只列出了 3 点，遗漏了"Performance Chart Gap"分析里已经给出的 Visual-only 规则改法。用户确认本计划要覆盖全部 4 类改进：

- **A**: Risk Assessment 一致性校验
- **B**: Chunk 截断参数优化
- **C**: Visual-only 冗余规则（prompt 层面区分"真实缺失"与"图表视觉冗余"）
- **D**: 补齐测试制品（`hyg-file-upload-test-result.md` / `hyg-file-upload-execution-diagram.html`）

## 目标

在不改变现有 graph 结构、TaskSpec、API 响应结构的前提下：

1. 让 `critical_issues` 与 `approval_status` / `auto_proceed` 的关系有代码层保障，不完全依赖 LLM 自洽。
2. 降低 chunk 边界截断导致的虚假 `critical_issues`。
3. 让图表类"视觉冗余"缺口不再被误判为需要人工审批的 `critical_issue`。
4. 让 `2026-07-02` 这次回归测试的制品目录完整，可作为后续对比基线。

---

## A. Risk Assessment 一致性校验

### 问题

[investment_document_review.py:94-114](../../../src/investory/agent_core/task_models/investment_document_review.py#L94-L114) 中的 `InvestmentDocumentReviewRiskAssessmentResult` 目前没有 `model_validator`，`overall_risk`、`critical_issues`、`approval_status`、`auto_proceed` 四个字段的一致性完全依赖 [investment_document_risk_assessment.md](../../../src/investory/agent_core/prompts/tasks/investment_document_risk_assessment.md) 的 prompt 约束（"`high` 风险必须有 `critical_issues`"，"`low`/`medium` 默认 `auto_proceed=true`"），LLM 可以在 `medium` 风险时以 `critical_issues` 非空为理由覆盖默认值，行为可预期但不是强制约束。

### 方案

在 `InvestmentDocumentReviewRiskAssessmentResult` 上新增 `model_validator(mode="after")`，**自动修复**不一致的字段组合，而不是直接抛出异常。修复规则按优先级顺序应用：

```python
from pydantic import model_validator

class InvestmentDocumentReviewRiskAssessmentResult(BaseModel):
    ...

    @model_validator(mode="after")
    def _fix_risk_consistency(self) -> "InvestmentDocumentReviewRiskAssessmentResult":
        # Rule 1: critical_issues non-empty ⟹ approval_status must be PENDING_HUMAN_APPROVAL
        if self.critical_issues and self.approval_status == InvestmentDocumentReviewApprovalStatus.AUTO_APPROVED:
            self.approval_status = InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL
        
        # Rule 2: approval_status == PENDING_HUMAN_APPROVAL ⟹ auto_proceed must be False
        if self.approval_status == InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL and self.auto_proceed:
            self.auto_proceed = False
        
        # Rule 3: overall_risk == HIGH ⟹ critical_issues must be non-empty
        if self.overall_risk == InvestmentDocumentReviewRiskLevel.HIGH and not self.critical_issues:
            self.critical_issues = ["Risk level is HIGH; requires human review due to unspecified critical concerns"]
        
        # Rule 4: approval_status == PENDING_HUMAN_APPROVAL ⟹ critical_issues must be non-empty
        if self.approval_status == InvestmentDocumentReviewApprovalStatus.PENDING_HUMAN_APPROVAL and not self.critical_issues:
            self.critical_issues = ["Approval is pending human review; auto-generated for consistency"]
        
        return self
```

修复逻辑遵循以下原则：
- **优先保持 LLM 意图**：尽量不改动 LLM 显式生成的字段值
- **自动同步衍生字段**：当主字段确定后，自动纠正依赖的衍生字段（如 `auto_proceed` 依赖 `approval_status`）
- **最小修复**：当某字段因逻辑要求必须有值时，补充通用的自动生成值（不引入业务逻辑判断）
- **无例外返回**：所有 LLM 输出都能通过，避免验证失败导致流程中断

### 失败路径影响

不再产生异常。所有 LLM 输出都会通过 `model_validator` 并返回修复后的结果。

[document_review_nodes.py:399-410](../../../src/investory/agent_core/runtime/flow/investment_document_review/document_review_nodes.py#L399-L410) 的 `try/except ValidationError` 处理逻辑仍然保留（防止其他可能的 Pydantic 错误），但 `model_validator` 修复后的输出不会触发异常路径。修复过程对调用方透明：

- 接收到 LLM 原始输出 → 自动修复 → 返回一致的结果对象
- 修复过程不产生日志、告警或额外副作用（纯数据变换）
- 流程始终返回 `ok=True`（除非存在其他 Pydantic 字段类型错误）

这种设计的优势是 LLM 可以"接近合理"的输出也被接纳，同时下游系统始终接收到逻辑一致的数据，无需担心字段组合的不合法性。

### 测试

在 [test_investment_document_review_task_model.py](../../../tests/test_investment_document_review_task_model.py) 中补充：

- `test_investment_document_review_risk_assessment_result_fixes_critical_issues_with_auto_approved`：输入有 `critical_issues` 但 `approval_status=AUTO_APPROVED`，验证输出被自动改为 `PENDING_HUMAN_APPROVAL`
- `test_investment_document_review_risk_assessment_result_fixes_auto_proceed_with_pending_approval`：输入 `approval_status=PENDING_HUMAN_APPROVAL` 但 `auto_proceed=true`，验证输出被自动改为 `false`
- `test_investment_document_review_risk_assessment_result_adds_default_critical_issue_for_high_risk`：输入 `overall_risk=HIGH` 但 `critical_issues=[]`，验证输出自动补充了一个 default critical issue
- `test_investment_document_review_risk_assessment_result_adds_default_critical_issue_for_pending_approval`：输入 `approval_status=PENDING_HUMAN_APPROVAL` 但 `critical_issues=[]`，验证输出自动补充了一个 default critical issue

四个用例均用 `assert` 直接验证修复后的字段值，无需 `pytest.raises`。测试样本基于合法的 LLM 输出形状，但字段值故意设成不一致的组合，验证修复后恢复一致性。

---

## B. Chunk 截断参数优化

### 问题

[document_chunker.py:7-8](../../../src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py#L7-L8):

```python
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
```

500 字符 chunk（约 80-100 英文单词）加 50 字符 overlap（10%），使 ETF factsheet 里常见的长披露句子在跨 chunk 边界时经常被切断，这是 `2026-07-02` 回归里 2 项 `critical_issues` 的直接原因。

### 方案

按笔记里的方案 1+2 组合调整参数：

```python
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
```

- `CHUNK_OVERLAP` 占比从 10% 提升到 15%，跨界句子更可能在至少一个 chunk 中完整出现。
- `CHUNK_SIZE` 从 500 提升到 1000，chunk 总数减少（预计从 25 降到 12-15），边界数量同步减少。
- `SELECT_MAX_CHARS`（[document_chunker.py:9](../../../src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py#L9)）保持 `4000` 不变，`select_relevant_chunks` 的容量语义不受影响。

不改动方案 3（邻近上下文传递）——payload 构造改动范围更大，且方案 1+2 已经是笔记里认定的"成本最低"组合，本次不引入。

### 测试

当前仓库没有针对 `document_chunker.py` 的直接单元测试（已检索 `tests/` 目录确认）。新增 `tests/test_document_chunker.py`，覆盖：

- `test_split_into_chunks_respects_chunk_size_and_overlap`：用一段可控长度的合成文本验证切出的 chunk 数量、每个 chunk 长度不超过 `CHUNK_SIZE`，相邻 chunk 之间有 overlap。
- `test_split_into_chunks_keeps_long_sentence_within_overlap_window`：构造一个略超过旧 `CHUNK_SIZE=500` 但小于新 `CHUNK_SIZE=1000` 的长句，断言切分后该句子完整出现在至少一个 chunk 里（回归验证本次改动确实缓解截断）。
- `test_select_relevant_chunks_respects_max_chars`：保留对现有 `select_relevant_chunks` 行为的基本覆盖（当前也没有测试），确认改动 `CHUNK_SIZE` 不破坏该函数。

### 回归影响

`chunk_count` 会整体下降（`hyg-file-upload` PDF 预计从 `25` 降到 `12-15`），进而影响：

- To-Do `task_count`（`chunk_count + analyze 维度数 + 1`）
- 部分现有测试如果硬编码了 `chunk_count=25` 或具体 `extract_chunk_00xx` 数量需要确认是否受影响。检索确认 [test_investment_document_review_flow.py](../../../tests/test_investment_document_review_flow.py) 中的 chunk 相关断言使用的是手工构造的 `state.document_chunks`（固定 2-3 个 mock chunk），不依赖 `split_into_chunks` 的真实切分结果，因此不受参数调整影响。

---

## C. Visual-only 冗余规则

### 问题

[pdf_extractor.py:26-29](../../../src/investory/gateway/pdf_extractor.py#L26-L29) 只做 `page.extract_text()`，无法捕获图表（如 `$10,000` 增长曲线）本身的视觉信息。但这类图表通常只是把已提取的文字/表格数据（如年度收益率）换成图形展示，并不包含额外数据维度。当前 [investment_document_extract.md](../../../src/investory/agent_core/prompts/tasks/investment_document_extract.md) 没有区分"真实数据缺失"和"视觉冗余缺失"，两者都被记入 `information_gaps`，进而传导到 `risk_assessment.critical_issues`，不必要地拉高风险判定。

### 方案

在 [investment_document_extract.md](../../../src/investory/agent_core/prompts/tasks/investment_document_extract.md) 的 Requirements 部分加入笔记中给出的规则文案：

```markdown
- Visual-only redundancy rule: If a graphical element (e.g., a performance growth
  chart, pie chart, or diagram) presents the same quantitative data that is
  otherwise available in extracted text, tables, or structured fields, note it
  under `boundary_notes` as "visual-only representation" rather than
  `information_gaps`. Example: "The $10,000 growth chart visualizes the same
  annual returns data already captured in the performance table; chart
  rendering details are not captured by text extraction."
```

插入位置：在现有 `- If a requested fact is not present, record it under information_gaps.` 之后，`- Keep boundary_notes focused on source limits...` 之前，保持要求项的逻辑顺序（先讲什么算 gap，再讲例外情况，再讲 boundary_notes 的范围）。

这条规则只影响 `investment_document_extract` 任务（chunk / 全文 extract 均适用），不改动 `investment_document_analyze.md` 或 `investment_document_synthesize.md` —— synthesize 任务本身会原样聚合 extract 结果里的 `boundary_notes`，规则在源头生效即可传导到最终结果。

### 测试

`tests/test_investment_document_review_todo_prompts.py` 里已有 `test_investment_document_extract_prompt_builds_messages`（[test_investment_document_review_todo_prompts.py:71](../../../tests/test_investment_document_review_todo_prompts.py#L71)），只验证 prompt 能正常渲染变量，不断言具体规则文案。新增一个轻量断言，确认新规则文案已经出现在渲染后的 prompt 里（防止未来编辑 prompt 时误删该规则）：

```python
def test_investment_document_extract_prompt_includes_visual_only_redundancy_rule() -> None:
    messages = build_prompt_messages("tasks", "investment_document_extract.md", {...})
    assert "visual-only representation" in messages[1].content
```

不新增端到端测试断言 LLM 输出（该规则的效果本身依赖 LLM 遵循 prompt，无法用单元测试验证语义效果，只能靠下一次 apifox 回归观察 `critical_issues` 数量变化）。

### 预期效果（需下一次 apifox 回归验证，不在本计划内断言）

若规则生效，`2026-07-02` 场景里"图表未见"的 `information_gap` 会改记为 `boundary_notes`，`risk_assessment.critical_issues` 从 3 项降到 2 项（剩下 2 项由 B 改进解决），`approval_status` 有机会从 `pending_human_approval` 变为 `auto_approved`。

---

## D. 补齐测试制品

### 问题

`test-results/hyg-file-upload/2026-07-02/` 目前只有 `hyg-file-upload-notes.md`、`hyg-file-upload-response.json`、`hyg-file-upload.log`，缺少 `hyg-file-upload-test-result.md` 和 `hyg-file-upload-execution-diagram.html`，不满足 [test-results/hyg-file-upload/README.md](../../../test-results/hyg-file-upload/README.md) 里描述的完整制品集合（对照 `2026-06-10-2.after-concurrency-fix/` 目录已有的四件套）。

### 方案

补充两个制品文件到 `test-results/hyg-file-upload/2026-07-02/`：

1. **`hyg-file-upload-test-result.md`**：参照 [2026-06-10-2.after-concurrency-fix/hyg-file-upload-test-result.md](../../../test-results/hyg-file-upload/2026-06-10-2.after-concurrency-fix/hyg-file-upload-test-result.md) 的结构（Test Artifact / Outcome / Task Breakdown / Timing Summary / Concurrency Reading / Interpretation），内容改为反映 `2026-07-02` 这次运行的实际结果：模块拆分后的回归验证、`risk_assessment` + 审批路由首次完整跑通、`pending_human_approval` 结果，以及与既往运行的任务结构对比。可直接从 [hyg-file-upload-notes.md](../../../test-results/hyg-file-upload/2026-07-02/hyg-file-upload-notes.md) 已有的"结果概览"和"时间分解"表格改写成叙述体，不需要重新分析日志。
2. **`hyg-file-upload-execution-diagram.html`**：参照 [2026-06-10-2.after-concurrency-fix/hyg-file-upload-execution-diagram.html](../../../test-results/hyg-file-upload/2026-06-10-2.after-concurrency-fix/hyg-file-upload-execution-diagram.html) 的时间轴可视化样式（extract/analyze/synthesize 三色分段 + 统计卡片），基于 `hyg-file-upload.log` 中的实际时间戳绘制 `2026-07-02` 这次运行的 extract fan-out、analyze 并发、synthesize、reflection、risk assessment 各阶段时间轴。需要新增一个 risk assessment 阶段的可视化分段（既往制品的图表模板里没有这个阶段，因为这是笔记里提到的"首次完整跑通审批路由"的记录）。

### 排序说明

D 项制品补齐应该在 A/B/C 代码改动**之后**完成，或者明确标注这份制品对应的是"改进前"的基线快照 —— 如果先做 D 再做 A/B/C，`test-result.md` 里的数字（`critical_issues=3`、`chunk_count=25`）会在改动后过时。建议顺序：

1. 先完成 D（补齐 `2026-07-02` 现有日志/响应对应的制品，作为"改进前基线"）
2. 再实施 A → B → C
3. 跑一次新的 apifox 回归，产出新的日期目录（如 `2026-07-03` 或当次实际日期），验证 `critical_issues` 数量下降、`chunk_count` 下降，并在 notes 里与 `2026-07-02` 基线对比

本计划的执行范围到"D 制品补齐 + A/B/C 代码改动 + 单元测试通过"为止，不包含第 3 步的新回归测试（新回归属于下一次验证工作，不在本次计划内启动服务或调用真实 LLM）。

---

## 实施步骤

1. **Step 1（D 优先）**: 补齐 `test-results/hyg-file-upload/2026-07-02/hyg-file-upload-test-result.md` 和 `hyg-file-upload-execution-diagram.html`，作为改进前基线快照。
2. **Step 2（A）**: 在 `investment_document_review.py` 的 `InvestmentDocumentReviewRiskAssessmentResult` 上新增 `model_validator`，实现自动修复逻辑，补充 4 个修复验证测试。
3. **Step 3（B）**: 调整 `document_chunker.py` 的 `CHUNK_SIZE=1000`、`CHUNK_OVERLAP=150`，新增 `tests/test_document_chunker.py`。
4. **Step 4（C）**: 在 `investment_document_extract.md` 加入 Visual-only redundancy rule，补充 prompt 渲染断言测试。
5. **Step 5（验证）**: 使用仓库 `.venv` 运行：
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/test_investment_document_review_task_model.py tests/test_document_chunker.py tests/test_investment_document_review_todo_prompts.py tests/test_investment_document_review_flow.py tests/test_investment_document_review_gateway_api.py
   ```
6. **Step 6（worklog）**: 在 `docs/2-2/worklog/` 新增 `17-chunk_truncation_and_visual_gap_improvement_execution_worklog.md`，记录每步改动、测试结果。

---

## 风险点

### 风险 1：自动修复可能掩盖 LLM 输出质量问题

通过自动修复避免了验证失败，但也可能让某些 LLM 输出的逻辑问题被无声地纠正而无法追踪。如果 LLM 频繁生成需要修复的不一致字段组合，说明 prompt 或模型的一致性理解有问题，应该在观察修复频率、建立监控告警（例如记录修复发生的情况）。

### 风险 2：自动生成的 critical_issues 可能过于通用

当 HIGH 风险或 PENDING_HUMAN_APPROVAL 但没有具体 critical_issues 时，自动补充的默认文案（"Risk level is HIGH; requires human review due to unspecified critical concerns"）是通用的占位符，可能掩盖了 LLM 实际应该提供的具体风险描述。下游系统和人工审批者会看到这个通用文案，可能影响决策质量。

### 风险 3：`CHUNK_SIZE` 调大后单次 extract 的 token 成本上升

笔记里已经评估："chunk 总数减少，总调用次数减少，可能抵偿"。本计划不引入额外的 token 用量监控，如果后续实测发现总成本不降反升，需要重新评估方案 1+2 与方案 3（邻近上下文传递）的取舍。

### 风险 4：Visual-only 规则可能被 LLM 过度使用，导致真实缺失被误判为"视觉冗余"

规则文案已经限定"presents the same quantitative data that is otherwise available"，即要求视觉元素对应的数据必须已经在文字/表格中出现才能降级为 `boundary_notes`。如果后续观察到误用，需要收紧措辞（例如要求引用具体的已提取数据点）。

---

## 验收标准

1. `InvestmentDocumentReviewRiskAssessmentResult` 自动修复 4 类不一致输入组合，4 个新增测试验证修复后的字段值正确，全部通过。
2. `document_chunker.py` 的 `CHUNK_SIZE=1000`、`CHUNK_OVERLAP=150`，新增的 `test_document_chunker.py` 三个测试通过。
3. `investment_document_extract.md` 包含 Visual-only redundancy rule 文案，新增的 prompt 渲染断言测试通过。
4. `test-results/hyg-file-upload/2026-07-02/` 目录补齐 `hyg-file-upload-test-result.md` 和 `hyg-file-upload-execution-diagram.html`。
5. 现有回归测试套件（`test_investment_document_review_flow.py`、`test_investment_document_review_gateway_api.py`、`test_investment_document_review_task_model.py`、`test_investment_document_review_todo_prompts.py`）全部通过。
6. Worklog 已更新，记录本次改动和验证结果。
