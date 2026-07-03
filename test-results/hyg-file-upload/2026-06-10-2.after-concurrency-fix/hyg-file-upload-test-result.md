# HYG File Upload Test Result

## Test Artifact

- Session ID: `apifox-hyg-file-upload`
- Source PDF: `data/hyg-ishares-iboxx-high-yield-corporate-bond-etf-fund-fact-sheet-en-us.pdf`
- Raw log extract: `test-results/hyg-file-upload/rerun-2026-06-10-after-concurrency-fix/apifox-hyg-file-upload.log`
- Baseline for comparison: `test-results/hyg-file-upload/baseline/`

## Outcome

The file upload review ran successfully from start to finish after the concurrency fix.

- `ok`: success from the logged task execution perspective
- `document_type`: `etf_factsheet`
- `chunk_count`: `25`
- `task_count`: `27`
- `failure_policy`: `retry_then_fail`
- `synthesis_produced`: `true`

Final completion line:

```text
investment_document_review.todo_execution.completed session_id=apifox-hyg-file-upload succeeded_count=27 failed_count=0 skipped_count=0 duration_ms=70022 synthesis_produced=true
```

## Task Breakdown

The plan contained:

- `25` extract tasks
- `1` aggregate analyze task
- `1` synthesize task

This still matches the logged plan summary:

```text
chunk_count=25 task_count=27
```

## Timing Summary

- Total execution time: `70022 ms` (`70.022 s`, about `1.17 min`)
- Extract task count: `25`
- Extract average duration: `5427 ms`
- Extract minimum duration: `3912 ms`
- Extract maximum duration: `8147 ms`
- Aggregate analyze duration: `9494 ms`
- Final synthesize duration: `14079 ms`

## Concurrency Reading

From this rerun log, the extract stage clearly executed in parallel.

Evidence:

- Three extract tasks start immediately at the beginning:

```text
extract_chunk_0001 started
extract_chunk_0002 started
extract_chunk_0003 started
```

- New extract tasks start as soon as one of those in-flight tasks finishes.
- Multiple extract tasks remain active at the same time for most of the extract stage.

Observed pattern:

```text
extract_chunk_0001 started
extract_chunk_0002 started
extract_chunk_0003 started
...
extract_chunk_0001 succeeded
extract_chunk_0004 started
extract_chunk_0002 succeeded
extract_chunk_0005 started
extract_chunk_0003 succeeded
extract_chunk_0006 started
...
```

Inference from the log shape:

- The extract worker pool is now behaving like a `3`-slot concurrent pipeline.
- The analyze task still waits for all `25` extract tasks to finish.
- The synthesize task still waits for analyze to finish.

## Baseline Comparison

Compared with the baseline run before the fix:

- Baseline total duration: `154366 ms`
- Rerun total duration: `70022 ms`
- Total reduction: `84344 ms`
- Total reduction percentage: `54.6%`
- Overall speedup: about `2.20x`

The biggest gain is in the extract stage wall-clock time.

- Baseline extract stage wall-clock: about `124.614 s`
- Rerun extract stage wall-clock: about `46.442 s`
- Extract stage speedup: about `2.68x`

## Interpretation

This was a clean success run with no retries, no failures, and no skipped tasks.

The concurrency fix appears to have worked as intended:

- The DAG already allowed extract fan-out.
- The runtime now actually uses that fan-out.
- The end-to-end latency dropped sharply without changing the task plan shape.

One important detail:

- Per-task extract latency did not become smaller on average.
- The improvement comes from overlapping independent extract tasks, not from each single extract becoming faster.

## Recommended Use

Use this rerun as the new reference for:

- validating `/investment-document-review-file`
- checking whether extract fan-out is truly active
- regression testing future flow/runtime changes
- comparing throughput before and after concurrency-related fixes

This sample is now much more practical as a medium-weight manual regression test because the total turnaround time dropped from about `2.57 min` to about `1.17 min`.
