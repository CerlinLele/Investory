# Rerun Notes

This folder is reserved for the HYG file upload rerun after the concurrency fix in:

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`

## Planned contents

- `apifox-hyg-file-upload.log`
- `hyg-file-upload-response.json`
- `hyg-file-upload-test-result.md`
- `hyg-file-upload-execution-diagram.html`

## What to compare against baseline

- Whether multiple `investment_document_review.todo_task.started` lines appear before earlier extract tasks finish.
- Whether extract-stage wall-clock time drops compared with the baseline run.
- Whether total review duration improves while preserving successful completion.

## Current result

Artifacts created for this rerun:

- `apifox-hyg-file-upload.log`
- `hyg-file-upload-test-result.md`
- `hyg-file-upload-execution-diagram.html`

High-level conclusion:

- The rerun shows real extract-stage concurrency.
- The end-to-end duration dropped from `154366 ms` to `70022 ms`.
- The overall speedup is about `2.20x`.
