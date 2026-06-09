# 用 Apifox 跑 `/investment-document-review` 和 `/investment-document-review-file`

## 测试时使用的接口路径

- JSON 请求接口：`POST http://127.0.0.1:8000/investment-document-review`
- 文件上传接口：`POST http://127.0.0.1:8000/investment-document-review-file`

以上两个路径与代码常量保持一致，定义位置见 `src/investory/gateway/api.py`：
- `INVESTMENT_DOCUMENT_REVIEW_ROUTE = "/investment-document-review"`
- `INVESTMENT_DOCUMENT_REVIEW_FILE_ROUTE = "/investment-document-review-file"`

## 当前公开 Graph 结构

Phase B-4 已完成，公开 graph 现在有两条主路径，由 `build_review_framework` 的 routing 决定：

```
START
  -> evaluate_policy_gate
  -> classify_document_type
  -> build_review_framework
       |
       ├─ document_chunks 非空 ──> generate_review_todo_plan
       │                              -> execute_review_todo_plan
       │                                   -> build_final_result
       │
       └─ document_chunks 为空 ──> run_single_pass_review
                                      -> build_final_result
```

Chunk 路径的 To-Do plan 结构固定为：

```
extract_chunk_0001  \
extract_chunk_0002   ├─ 所有 chunk extract 任务
...                 /
  -> analyze_aggregated_chunk_evidence
  -> synthesize_full_document_review
```

两个公开 endpoint：

| endpoint | 请求格式 | 入口 |
|---|---|---|
| `POST /investment-document-review` | JSON body | `run_investment_document_review()` |
| `POST /investment-document-review-file` | multipart/form-data | `run_investment_document_review_file()` |

两个 endpoint 共享同一个 `execute_investment_document_review_request()` -> flow。

## 服务启动

```powershell
.\.venv\Scripts\python.exe -m uvicorn investory.main:app --reload
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

## 服务端日志观察点

手工跑 Apifox 用例时，同时观察控制台输出和 `logs/investory.log`。

日志文件位置：

- `logs/investory.log`

建议观察的稳定事件名：

- `investment_document_review.todo_plan.generated`
- `investment_document_review.todo_execution.started`
- `investment_document_review.todo_task.started`
- `investment_document_review.todo_task.retrying`
- `investment_document_review.todo_task.succeeded`
- `investment_document_review.todo_task.failed`
- `investment_document_review.todo_task.skipped`
- `investment_document_review.todo_execution.completed`
- `investment_document_review.todo_resume.loaded`
- `investment_document_review.todo_resume.saved`

按场景看日志时可以重点关注：

- Case 3 短文本 chunk review：通常能看到 `task_count=3`，以及一条 extract、一条 analyze、一条 synthesize 的生命周期日志。
- Case 5 多 chunk review：通常能看到多个 `extract_chunk_000x` 任务先执行，再进入聚合 analyze 和最终 synthesize。
- 失败场景：重点看 `investment_document_review.todo_task.failed` 里的 `task_id`、`task_kind`、`error_type`、`stage`。
- resume 场景：如果后续接入 resume store，重点看 `todo_resume.loaded` 和 `todo_resume.saved` 里的结果数量。

建议检索关键词：

```text
investment_document_review.todo_
session_id=apifox-
task_id=extract_chunk_
```

日志判读注意点：

- INFO 日志默认不应包含完整 `document_text`、完整 prompt 或完整模型输出。
- 并发或分层执行时，日志顺序不一定严格等于 plan 顺序，优先用 `session_id` 和 `task_id` 关联。
- `todo_execution.completed` 出现时，可以快速判断本次请求的 succeeded/failed/skipped 数量，以及是否产出了最终 synthesis。

## JSON Endpoint Test Cases

Apifox 里这一组测试统一使用：

```text
POST http://127.0.0.1:8000/investment-document-review
Content-Type: application/json
```

### Case 1: Missing Input — 不需要 LLM key

```json
{
  "payload": {
    "review_goal": "Check fees"
  },
  "session_id": "apifox-missing-input"
}
```

预期：

```json
{
  "ok": true,
  "task_name": "investment_document_review",
  "result": {
    "action": "ask_for_missing_input",
    "missing_fields": ["document_text"]
  },
  "error": null
}
```

### Case 2: Refusal — 不需要 LLM key

```json
{
  "payload": {
    "document_text": "ETF factsheet with fee table and index tracking details.",
    "review_goal": "Should I buy this ETF today?"
  },
  "session_id": "apifox-refusal"
}
```

预期：

```json
{
  "ok": true,
  "result": {
    "action": "refuse_and_redirect"
  },
  "error": null
}
```

### Case 3: Short Text — Single-Pass Review — 需要 LLM key

文档文本短于 `CHUNK_SIZE=500` 字符时，`split_into_chunks()` 返回单个 chunk，`document_chunks` 非空，**仍然走 chunk 路径**（extract x1 -> analyze -> synthesize）。

这是与旧测试计划的核心差异：除非 `document_text` 为空，否则现在几乎所有有效输入都走 chunk 路径。

> 注：`route_after_review_framework` 在 `document_chunks` 非空时路由到 `GENERATE_REVIEW_TODO_PLAN`。长度 > 0 的任何有效文本都会产生至少一个 chunk。

```json
{
  "payload": {
    "document_text": "ETF Factsheet. The fund tracks the Example 500 Index. The management fee is 0.10% per year. The document states that past performance is not a reliable indicator of future performance. It lists holdings across technology, healthcare, and financial sectors.",
    "document_type_hint": "etf_factsheet",
    "review_goal": "Review fee clarity and risk disclosure completeness"
  },
  "session_id": "apifox-short-doc-chunk-review"
}
```

预期（chunk 路径产出，`review` 字段内容为合成结果而非 single-pass 结果）：

```json
{
  "ok": true,
  "task_name": "investment_document_review",
  "result": {
    "action": "complete",
    "document_type": "etf_factsheet",
    "route_reason": "...",
    "route_confidence": 0.0,
    "review": {
      "document_type": "etf_factsheet",
      "extracted_facts": [],
      "risk_findings": [],
      "information_gaps": [],
      "boundary_notes": [],
      "summary": "..."
    }
  },
  "error": null
}
```

断言要点：
- `result.action == "complete"`
- `result.document_type == "etf_factsheet"`
- `result.review` 存在且非 null
- `route_confidence` 在 `0..1` 范围内，不断言具体值

### Case 4: Unknown Document Type — 需要 LLM 分类参与

```json
{
  "payload": {
    "document_text": "A short unlabeled investment note with insufficient context."
  },
  "session_id": "apifox-unknown-type"
}
```

预期：

```json
{
  "ok": true,
  "result": {
    "action": "ask_for_missing_input",
    "missing_fields": ["document_type_hint"]
  },
  "error": null
}
```

### Case 5: Long Document — Multi-Chunk Review — 需要 LLM key

文档 > 500 字符，产生多个 chunks，To-Do plan 中包含 `extract_chunk_0001`、`extract_chunk_0002`...

```json
{
  "payload": {
    "document_text": "[粘贴从真实 ETF factsheet PDF 提取的全文，约 1000-3000 字符]",
    "document_type_hint": "etf_factsheet",
    "review_goal": "Review fee, risk disclosure, and liquidity constraints"
  },
  "session_id": "apifox-multi-chunk-review"
}
```

预期行为（不断言具体 LLM 文本内容）：
- `result.action == "complete"`
- `result.review` 非 null，且 `result.review.extracted_facts` / `risk_findings` / `information_gaps` 有内容
- 响应时间明显长于 Case 3，因为每个 chunk 都调用了一次 extract LLM

---

## File Upload Endpoint Test Cases

### Case 6: PDF Upload — Valid ETF Factsheet — 需要 LLM key

```text
Method: POST
URL: http://127.0.0.1:8000/investment-document-review-file
Content-Type: multipart/form-data
```

Apifox Body 字段：

| Key | Type | Value |
|---|---|---|
| `file` | File | 选择本地 ETF factsheet PDF |
| `review_goal` | Text | `Review fee clarity and risk disclosure completeness` |
| `document_type_hint` | Text | `etf_factsheet` |
| `session_id` | Text | `apifox-file-upload-valid` |

预期：等价于 Case 3 / Case 5 的 `action: complete` 响应，具体取决于 PDF 提取后文本长度。

### Case 7: PDF Upload — Corrupted File — 不需要 LLM key

上传损坏文件（可以把任意文本文件改后缀为 `.pdf`，或构造一个无效 PDF 头的文件）。

预期（HTTP 400）：

```json
{
  "ok": false,
  "task_name": null,
  "session_id": "...",
  "result": null,
  "error": {
    "error_type": "pdf_extraction_failed",
    "stage": "input_validation",
    "retryable": false
  }
}
```

### Case 8: No File Field — FastAPI Validation — 不需要 LLM key

发送 multipart 请求但不包含 `file` 字段。

预期（HTTP 422，FastAPI 自动返回）：

```json
{
  "detail": [...]
}
```

不走 flow，FastAPI dependency injection 在 request 解析阶段即返回 422。

---

## Apifox 断言建议

只断言以下稳定字段，不断言模型生成文本：

```
ok                   (bool)
task_name            (string | null)
session_id           (string, 非空)
result.action        ("ask_for_missing_input" | "refuse_and_redirect" | "complete")
result.missing_fields  (list, 仅 ask_for_missing_input 时)
result.document_type   (string, 仅 complete 时)
result.review          (object, 仅 complete 时)
error                (null 或包含 error_type)
```

---

## 真实测试文档来源

- [iShares（BlackRock）](https://www.ishares.com/us/products/etf-investments) — ETF factsheet PDF
- [Vanguard](https://investor.vanguard.com/investment-products/etfs) — fund fact sheet PDF
- [SPDR（State Street）](https://www.ssga.com/us/en/intermediary/etfs)
- [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar) — N-1A / S-1 共同基金招募说明书

JSON endpoint 可直接粘贴 PDF 提取文本；File endpoint 直接上传 PDF 文件。

---

## 与旧测试计划的主要差异

| 变化点 | 旧测试计划 | 当前实现 |
|---|---|---|
| 主路径 | single-pass review | chunk 路径（任何非空文档） |
| single-pass 触发条件 | 已分类文档均走此路径 | `document_chunks` 为空才走（实际几乎不触发） |
| File upload endpoint | 不存在 | `/investment-document-review-file` (multipart) |
| To-Do DAG | 未接入公开 graph | 已是公开主路径 |
| `result.review` 来源 | single-pass task 直接输出 | synthesize task 输出（经过 extract -> analyze 聚合） |
