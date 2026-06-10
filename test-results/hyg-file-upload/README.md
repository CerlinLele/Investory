# HYG File Upload Test Results

This directory stores repeated test runs for the `hyg-file-upload` scenario.

## Structure

- `baseline/`
  - The original run before the concurrency fix.
- `rerun-2026-06-10-after-concurrency-fix/`
  - Reserved for the next rerun after the `asyncio.to_thread(...)` fix.

## Suggested files for each run

- `apifox-hyg-file-upload.log`
  - Extracted log lines for the run.
- `hyg-file-upload-response.json`
  - Raw API response payload.
- `hyg-file-upload-test-result.md`
  - Human-readable summary of findings.
- `hyg-file-upload-execution-diagram.html`
  - Execution diagram showing task ordering and overlap.
- `notes.md`
  - Test conditions, code version, and comparison notes.

## Naming convention for future reruns

Create a new sibling folder like:

- `rerun-YYYY-MM-DD-short-description/`

Example:

- `rerun-2026-06-11-retest-after-prompt-tuning/`
