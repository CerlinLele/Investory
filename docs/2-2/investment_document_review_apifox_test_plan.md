# 用 Apifox 跑 `/investment-document-review`

## Summary

目标是在 Apifox 里验证当前公开网关流程：`POST /investment-document-review`。当前公开 endpoint 的请求结构是：

```json
{
  "payload": {},
  "session_id": "optional-session-id"
}
```

响应结构固定为：

```json
{
  "ok": true,
  "task_name": "investment_document_review",
  "session_id": "...",
  "result": {},
  "error": null
}
```

注意：当前公开 FastAPI graph 仍走 `policy gate -> classify_document_type -> build framework -> single-pass review -> final result`。Phase 5 的 To-Do DAG 能力已有内部方法和测试覆盖，但还没有接到公开 endpoint 的主 graph 上。

## 当前公开 FastAPI graph 代码定位

公开入口从 FastAPI app 注入的 flow 开始：

```text
src/investory/main.py:21
create_app()
  -> app.state.investment_document_review_flow = build_investment_document_review_flow()
```

HTTP endpoint 在 gateway 层：

```text
src/investory/gateway/api.py:33
INVESTMENT_DOCUMENT_REVIEW_ROUTE = "/investment-document-review"

src/investory/gateway/api.py:151
@router.post(INVESTMENT_DOCUMENT_REVIEW_ROUTE, response_model=TaskResponse)
run_investment_document_review()
  -> getattr(request.app.state, "investment_document_review_flow", None)
  -> execute_investment_document_review_request()
  -> flow.run(review_request.payload, session_id=session_id)
```

当前公开 graph 的实际编排在：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:294
InvestmentDocumentReviewFlow._build_graph()
```

当前 `_build_graph()` 接入的主路径是：

```text
START
  -> evaluate_policy_gate
  -> classify_document_type
  -> build_review_framework
  -> run_single_pass_review
  -> build_final_result
  -> END
```

对应代码锚点：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:310
graph.add_node(... RUN_SINGLE_PASS_REVIEW ..., self.run_single_pass_review)

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:346
BUILD_REVIEW_FRAMEWORK -> RUN_SINGLE_PASS_REVIEW

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:349
RUN_SINGLE_PASS_REVIEW -> BUILD_FINAL_RESULT

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:431
run_single_pass_review()
```

To-Do DAG 相关节点和方法已经在代码里存在，但当前没有接入 `_build_graph()` 的公开主路径：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:105
GENERATE_REVIEW_TODO_PLAN = "generate_review_todo_plan"

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:106
EXECUTE_REVIEW_TODO_PLAN = "execute_review_todo_plan"

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:441
generate_review_todo_plan()

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:467
execute_review_todo_plan()
```

所以用 Apifox 跑公开 endpoint 时，当前验证的是 gateway + policy/classification + single-pass review 公开链路；不是 Phase 5 To-Do DAG 的公开链路。

## Apifox Setup

1. 在仓库根目录启动服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn investory.main:app --reload
```

2. Apifox 新建请求：

```text
Method: POST
URL: http://127.0.0.1:8000/investment-document-review
Headers:
Content-Type: application/json
```

3. 可先用健康检查确认服务活着：

```text
GET http://127.0.0.1:8000/health
```

## Test Cases

### Case 1: Missing Input, 不需要 LLM key

用于确认 policy gate 缺字段分支。

```json
{
  "payload": {
    "review_goal": "Check fees"
  },
  "session_id": "apifox-missing-input"
}
```

预期重点：

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

### Case 2: Refusal, 不需要 LLM key

用于确认投资建议越界请求会在 router/executor 前被拒绝。

```json
{
  "payload": {
    "document_text": "ETF factsheet with fee table and index tracking details.",
    "review_goal": "Should I buy this ETF today?"
  },
  "session_id": "apifox-refusal"
}
```

预期重点：

```json
{
  "ok": true,
  "result": {
    "action": "refuse_and_redirect"
  },
  "error": null
}
```

### Case 3: Full Review, 需要 LLM key

这个会调用 LLM router 和 single-pass review task。先确保 `.env` 或环境变量里有对应 provider key，比如默认 OpenAI：

```text
OPENAI_API_KEY=...
```

请求体：

```json
{
  "payload": {
    "document_text": "ETF Factsheet. The fund tracks the Example 500 Index. The management fee is 0.10% per year. The document states that past performance is not a reliable indicator of future performance. It lists holdings across technology, healthcare, and financial sectors.",
    "document_type_hint": "etf_factsheet",
    "review_goal": "Review fee clarity and risk disclosure completeness"
  },
  "session_id": "apifox-complete-review"
}
```

预期重点：

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

`route_confidence` 会由模型输出决定，不要固定断言具体数值，只断言它存在并在 `0..1` 范围内。

### Case 4: Unknown Document Type, 需要 LLM 分类参与

用于验证 Phase 6 修复点：unknown 时应返回 `document_type_hint`。

```json
{
  "payload": {
    "document_text": "A short unlabeled investment note with insufficient context."
  },
  "session_id": "apifox-unknown-type"
}
```

预期重点：

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

## 真实测试文档来源

`document_text` 是普通字符串字段，直接接受文字内容，不是文件上传。拿到 PDF 后用任意工具（Adobe、pdfplumber、pdfminer）提取文字层粘贴进来即可。ETF factsheet 通常 1-3 页，提取后约 500-1500 字，对 single-pass review 来说信息密度足够。

### ETF Factsheet（直接对应 `etf_factsheet` 类型）

- [iShares（BlackRock）](https://www.ishares.com/us/products/etf-investments) — 每只产品页都有 PDF factsheet，含费率、指数追踪、持仓分布、风险披露
- [Vanguard](https://investor.vanguard.com/investment-products/etfs) — 提供 fund fact sheet PDF
- [SPDR（State Street）](https://www.ssga.com/us/en/intermediary/etfs) — 标准化 factsheet

### 基金招募说明书 / Prospectus

- [SEC EDGAR](https://www.sec.gov/cgi-bin/browse-edgar) — 美国所有公开基金的法定披露文件，搜 N-1A（共同基金）或 S-1

### 香港 / 亚洲市场

- [香港证监会基金认可列表](https://apps.sfc.hk/cgi-bin/fund/cgi/html/fundSearch.cgi) — 授权基金招股说明书和年报
- [富达香港](https://www.fidelity.com.hk/)、[先锋香港](https://www.vanguard.com.hk/) — 中英文 factsheet

## Assumptions

- 默认本地服务地址是 `http://127.0.0.1:8000`。
- 如果只想先确认 endpoint 和兼容分支，跑 Case 1 和 Case 2 就够，不需要 LLM key。
- 如果要跑完整审查结果，必须配置 LLM provider key；当前默认 provider 是 `openai`，默认读取 `OPENAI_API_KEY`。
- Apifox 断言建议只检查稳定字段：`ok`、`task_name`、`session_id`、`result.action`、`error`，不要断言模型生成文本的完整内容。
