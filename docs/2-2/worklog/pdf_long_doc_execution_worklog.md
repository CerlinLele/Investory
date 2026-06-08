# PDF Long Document Execution Worklog

## 2026-06-08T00:00:00+10:00 Step A-1

- Step: Step A-1 - add PDF upload dependencies.
- Commands/actions:
  - Inspected dependency versions for `pdfplumber` and `python-multipart` from the repository `.venv`.
  - Confirmed both selected versions are the latest available versions from the package index.
  - Staged the dependency update for `pyproject.toml` when processing Step A-1.
- Files touched:
  - `pyproject.toml`
  - `docs/2-2/worklog/pdf_long_doc_execution_worklog.md`
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
  - `docs/2-2/worklog/pdf_long_doc_execution_worklog.md`
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
  - `docs/2-2/worklog/pdf_long_doc_execution_worklog.md`
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
  - `docs/2-2/worklog/pdf_long_doc_execution_worklog.md`
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