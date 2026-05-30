# /learning-entry Apifox Smoke Examples

This document gives the minimum Apifox calls for verifying the LangGraph
learning entry flow.

## Service Setup

Start the local API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn investory.main:app --reload
```

Use this base URL in Apifox:

```text
http://127.0.0.1:8000
```

Common request settings:

- Method: `POST`
- Path: `/learning-entry`
- Header: `Content-Type: application/json`

The missing-field and refusal branches do not call the downstream task model.
The QA learning task branch does call the existing `TaskExecutor`, so it needs
valid LLM provider configuration.

## Smoke 1: Missing Field Branch

Purpose: verify `question` without `material_text` returns a request for more
input and does not execute a task.

Body:

```json
{
  "session_id": "apifox-missing-1",
  "payload": {
    "question": "What is an ETF?"
  }
}
```

Expected response markers:

```json
{
  "ok": true,
  "task_name": "learning_entry",
  "session_id": "apifox-missing-1",
  "result": {
    "action": "ask_for_missing_input",
    "missing_fields": ["material_text"]
  },
  "error": null
}
```

## Smoke 2: Investment Advice Refusal Branch

Purpose: verify direct buy/sell style requests are redirected before task
execution.

Body:

```json
{
  "session_id": "apifox-refusal-1",
  "payload": {
    "material_text": "VOO is an ETF that tracks the S&P 500.",
    "question": "Should I buy VOO tomorrow?"
  }
}
```

Expected response markers:

```json
{
  "ok": true,
  "task_name": "learning_entry",
  "session_id": "apifox-refusal-1",
  "result": {
    "action": "refuse_and_redirect",
    "suggested_learning_direction": "..."
  },
  "error": null
}
```

## Smoke 3: QA Learning Task Branch

Purpose: verify a complete learning QA request is routed to the existing
`finance_qa` task through `TaskExecutor`.

Body:

```json
{
  "session_id": "apifox-qa-1",
  "payload": {
    "material_text": "An ETF is an exchange-traded fund. It can hold a basket of assets such as stocks or bonds and trades on an exchange during market hours.",
    "question": "What is an ETF?"
  }
}
```

Expected response markers when the model call succeeds:

```json
{
  "ok": true,
  "task_name": "finance_qa",
  "session_id": "apifox-qa-1",
  "result": {
    "answer": "...",
    "concept_explanation": "...",
    "evidence": ["..."],
    "common_misunderstandings": ["..."],
    "risk_notice": "...",
    "uncertainty": "..."
  },
  "error": null
}
```

If provider credentials or model configuration are missing, this branch may
return `ok: false` with a populated `error`. That still confirms the request
reached the executable learning branch if `task_name` is `finance_qa`.
