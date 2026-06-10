# PDF Long Document Execution Worklog

## 2026-06-08T00:00:00+10:00 Step A-1

- Step: Step A-1 - add PDF upload dependencies.
- Commands/actions:
  - Inspected dependency versions for `pdfplumber` and `python-multipart` from the repository `.venv`.
  - Confirmed both selected versions are the latest available versions from the package index.
  - Staged the dependency update for `pyproject.toml` when processing Step A-1.
- Files touched:
  - `pyproject.toml`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Added `pdfplumber==0.11.9` for PDF text extraction.
  - Added `python-multipart==0.0.32` for FastAPI `multipart/form-data` upload parsing.
  - Kept exact pinned dependency style consistent with the existing `pyproject.toml` dependencies.
- Evidence anchors:
  - `pyproject.toml:15`
  - `pyproject.toml:17`
  - Version check evidence: `.venv\Scripts\python.exe -m pip index versions pdfplumber` reported `LATEST: 0.11.9`.
  - Version check evidence: `.venv\Scripts\python.exe -m pip index versions python-multipart` reported `LATEST: 0.0.32`.

## 2026-06-08T00:00:00+10:00 Step A-2

- Step: Step A-2 - add gateway PDF text extraction utility.
- Commands/actions:
  - Reviewed `src/investory/gateway/pdf_extractor.py`.
  - Updated the extractor implementation after product clarification that PDF review must preserve full extracted text rather than truncating at the gateway layer.
  - Ran linter diagnostics for `src/investory/gateway/pdf_extractor.py`.
- Files touched:
  - `src/investory/gateway/pdf_extractor.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Added `extract_text_from_pdf(file_bytes: bytes) -> str` for gateway-side PDF text extraction.
  - The extractor opens PDFs from memory via `pdfplumber.open(io.BytesIO(file_bytes))`, extracts text page by page, skips empty pages, joins pages with blank-line separation, and collapses excessive blank lines.
  - Removed the earlier `max_chars` truncation design because complete document review should not silently discard later PDF content at the upload boundary.
  - Kept explicit failure behavior: missing `pdfplumber` raises `RuntimeError`, while unreadable PDFs or PDFs with no extractable text raise `ValueError` for the endpoint to convert into a 400 response.
- Evidence anchors:
  - `src/investory/gateway/pdf_extractor.py:9`
  - `src/investory/gateway/pdf_extractor.py:19`
  - `src/investory/gateway/pdf_extractor.py:23`
  - `src/investory/gateway/pdf_extractor.py:34`
  - `src/investory/gateway/pdf_extractor.py:40`
  - Lint evidence: `ReadLints` on `src/investory/gateway/pdf_extractor.py` (no diagnostics)

## 2026-06-08T00:00:00+10:00 Step A-3

- Step: Step A-3 - add multipart upload request schema for investment document review PDFs.
- Commands/actions:
  - Reviewed `src/investory/gateway/schemas.py`.
  - Inspected the unstaged diff for `src/investory/gateway/schemas.py`.
  - Ran linter diagnostics for `src/investory/gateway/schemas.py`.
- Files touched:
  - `src/investory/gateway/schemas.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Added `InvestmentDocumentReviewFileUploadRequest` as a plain dependency-injection class instead of a Pydantic `FlowRequest` subclass.
  - Added `UploadFile` and `Form` fields for the PDF file, optional review goal, optional document type hint, and optional session id.
  - Exported `InvestmentDocumentReviewFileUploadRequest` through `__all__` for use by the gateway endpoint.
  - Kept JSON request schemas unchanged so existing `/investment-document-review` behavior remains separate from multipart upload parsing.
- Evidence anchors:
  - `src/investory/gateway/schemas.py:7`
  - `src/investory/gateway/schemas.py:59`
  - `src/investory/gateway/schemas.py:66`
  - `src/investory/gateway/schemas.py:73`
  - `src/investory/gateway/schemas.py:109`
  - Lint evidence: `ReadLints` on `src/investory/gateway/schemas.py` (no diagnostics)

## 2026-06-08T00:00:00+10:00 Step A-4

- Step: Step A-4 - add PDF upload endpoint for investment document review.
- Commands/actions:
  - Reviewed `src/investory/gateway/api.py`.
  - Inspected the unstaged diff for `src/investory/gateway/api.py`.
  - Ran linter diagnostics for `src/investory/gateway/api.py`.
- Files touched:
  - `src/investory/gateway/api.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Added `INVESTMENT_DOCUMENT_REVIEW_FILE_ROUTE = "/investment-document-review-file"`.
  - Added `run_investment_document_review_file()` as an async multipart upload endpoint using `InvestmentDocumentReviewFileUploadRequest = Depends()`.
  - Reads the uploaded file bytes asynchronously, extracts full PDF text with `extract_text_from_pdf()`, and injects it into the existing investment document review payload as `document_text`.
  - Preserves optional `review_goal`, `document_type_hint`, and `session_id` fields from the multipart request.
  - Converts PDF extraction failures into a 400 `TaskResponse` with `error_type="pdf_extraction_failed"` and does not enter the review flow on extraction failure.
  - Reuses `execute_investment_document_review_request()` so the file endpoint shares the same flow behavior as the JSON endpoint after text extraction.
- Evidence anchors:
  - `src/investory/gateway/api.py:5`
  - `src/investory/gateway/api.py:19`
  - `src/investory/gateway/api.py:22`
  - `src/investory/gateway/api.py:36`
  - `src/investory/gateway/api.py:166`
  - `src/investory/gateway/api.py:177`
  - `src/investory/gateway/api.py:188`
  - `src/investory/gateway/api.py:202`
  - Lint evidence: `ReadLints` on `src/investory/gateway/api.py` (no diagnostics)

## 2026-06-08T00:00:00+10:00 Step B-1

- Step: Step B-1 - add document chunking utilities for long document review internals.
- Commands/actions:
  - Reviewed `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py`.
  - Checked `langchain-text-splitters` availability from the repository `.venv`; it was missing before installation.
  - Checked available package versions and selected `langchain-text-splitters==1.1.2`.
  - Installed `langchain-text-splitters==1.1.2` into the repository `.venv`.
  - Verified `RecursiveCharacterTextSplitter` imports successfully from `.venv`.
  - Ran a minimal chunking smoke check through `split_into_chunks()`.
- Files touched:
  - `pyproject.toml`
  - `requirements.lock.txt`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Replaced the hand-written paragraph chunking implementation with LangChain's `RecursiveCharacterTextSplitter`.
  - Added `langchain-text-splitters==1.1.2` to project dependencies and the lock file.
  - Added module-level defaults `CHUNK_SIZE = 500`, `CHUNK_OVERLAP = 50`, `SELECT_MAX_CHARS = 4000`, and `CHUNK_SEPARATORS`.
  - Kept the public `split_into_chunks()` and `select_relevant_chunks()` interfaces unchanged for the flow integration.
  - Kept keyword-scored chunk selection with original document order restored before joining.
  - Kept empty-input fallback returning an empty string/list and no-keyword-match fallback returning leading chunks up to the selection limit.
- Evidence anchors:
  - `pyproject.toml:15`
  - `requirements.lock.txt:25`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py:5`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py:8`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py:15`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py:25`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py:43`
  - Version check evidence: `.venv\Scripts\python.exe -m pip index versions langchain-text-splitters` reported `LATEST: 1.1.2`.
  - Import evidence: `.venv\Scripts\python.exe -c "from langchain_text_splitters import RecursiveCharacterTextSplitter; print(RecursiveCharacterTextSplitter.__name__)"` printed `RecursiveCharacterTextSplitter`.
  - Smoke evidence: `.venv\Scripts\python.exe -c "from investory.agent_core.runtime.flow.investment_document_review.document_chunker import split_into_chunks; chunks = split_into_chunks('A paragraph.\n\n' + 'B ' * 400, chunk_size=120); print(len(chunks)); print(all(chunk.strip() for chunk in chunks))"` printed `12` and `True`.

## 2026-06-08T00:00:00+10:00 Step B-2

- Step: Step B-2 - add document chunks to investment document review state.
- Commands/actions:
  - Reviewed `src/investory/agent_core/contracts/investment_document_review_state.py`.
  - Inspected the unstaged diff for `src/investory/agent_core/contracts/investment_document_review_state.py`.
  - Ran linter diagnostics for `src/investory/agent_core/contracts/investment_document_review_state.py`.
- Files touched:
  - `src/investory/agent_core/contracts/investment_document_review_state.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Added `document_chunks: list[str] = Field(default_factory=list)` to `InvestmentDocumentReviewState`.
  - Kept the default as an empty list so existing single-pass review paths and tests can instantiate state without providing chunk data.
  - Did not add evidence aggregation state in this step; that remains a later integration concern for per-chunk extraction and synthesis.
- Evidence anchors:
  - `src/investory/agent_core/contracts/investment_document_review_state.py:50`
  - Lint evidence: `ReadLints` on `src/investory/agent_core/contracts/investment_document_review_state.py` (no diagnostics)

## 2026-06-08T00:00:00+10:00 Step B-3

- Step: Step B-3 - build document chunks in `build_review_framework`.
- Commands/actions:
  - Reviewed `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`.
  - Removed the earlier keyword-filtering `select_relevant_chunks()` hookup from extract/analyze payload builders because the updated plan requires full chunk coverage.
  - Inspected the diff for `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`.
  - Ran linter diagnostics for `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`.
- Files touched:
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Imported `split_into_chunks()` into the investment document review flow.
  - Added document chunk construction at the end of `build_review_framework` from `state.input_payload[DOCUMENT_TEXT_FIELD]`.
  - Returned `document_chunks` alongside `review_framework` and `review_payload` so the state can carry precomputed chunks for later per-chunk extract work.
  - Kept existing extract/analyze To-Do payload builders on their original full-text behavior for this step; per-chunk extraction remains a later Step B-4 concern.
- Evidence anchors:
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:29`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:429`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:435`
  - Lint evidence: `ReadLints` on `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py` (no diagnostics)

## 2026-06-08T00:00:00+10:00 Step B-4

- Step: Step B-4 - add per-chunk extract and evidence aggregation review path.
- Commands/actions:
  - Reviewed `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py` and the To-Do task input model.
  - Added a chunk-aware graph branch after `build_review_framework` so non-empty `document_chunks` enter To-Do execution instead of the single-pass review path.
  - Added a deterministic chunk review To-Do plan builder that creates one extract task per chunk, then an aggregate analyze task, then a final synthesize task.
  - Updated extract task payload/model/prompt handling so chunk extraction receives `document_text`, `chunk_index`, `chunk_count`, and `review_scope="document_chunk"`.
  - Updated the flow test that previously asserted single-pass execution for known documents to assert chunk extract -> analyze -> synthesize execution.
  - Ran focused pytest coverage for the changed flow, task model, and prompt behavior.
- Files touched:
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`
  - `src/investory/agent_core/task_models/investment_document_review_todo_tasks.py`
  - `src/investory/agent_core/prompts/tasks/investment_document_extract.md`
  - `tests/test_investment_document_review_flow.py`
  - `docs/2-2/worklog/afterclass-pdf_long_doc_execution_worklog.md`
- Result:
  - Main review flow now covers all chunks through a map-reduce style path: every chunk gets a lightweight extract task, all chunk extracts feed an aggregate analyze task, and the final synthesize task produces the review output.
  - `document_chunks` empty remains the fallback route to existing single-pass review behavior.
  - Existing manually constructed To-Do extract payloads remain backward compatible because default full-document chunk metadata is excluded from dumped payloads.
  - The extract prompt now explicitly treats `document_chunk` scope as chunk-local evidence extraction.
- Evidence anchors:
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:88`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:370`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:493`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:518`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:624`
  - `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py:827`
  - `src/investory/agent_core/task_models/investment_document_review_todo_tasks.py:34`
  - `src/investory/agent_core/prompts/tasks/investment_document_extract.md:6`
  - Test evidence: `.venv\Scripts\python.exe -m pytest tests\test_investment_document_review_flow.py::test_document_review_flow_executes_known_document_review_task tests\test_investment_document_review_flow.py::test_execute_review_todo_plan_dispatches_extract_tasks_through_executor tests\test_investment_document_review_todo_task_models.py tests\test_investment_document_review_todo_prompts.py -q` (11 passed)
