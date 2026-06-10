# HYG File Upload Test Result

## Test Artifact

- Session ID: `apifox-hyg-file-upload`
- Source PDF: `data/hyg-ishares-iboxx-high-yield-corporate-bond-etf-fund-fact-sheet-en-us.pdf`
- Raw log extract: `test-results/hyg-file-upload/apifox-hyg-file-upload.log`

## Outcome

The file upload review ran successfully from start to finish.

- `ok`: success from the logged task execution perspective
- `document_type`: `etf_factsheet`
- `chunk_count`: `25`
- `task_count`: `27`
- `failure_policy`: `retry_then_fail`
- `synthesis_produced`: `true`

Final completion line:

```text
investment_document_review.todo_execution.completed session_id=apifox-hyg-file-upload succeeded_count=27 failed_count=0 skipped_count=0 duration_ms=154366 synthesis_produced=true
```

## Task Breakdown

The plan contained:

- `25` extract tasks
- `1` aggregate analyze task
- `1` synthesize task

This matches the logged plan summary:

```text
chunk_count=25 task_count=27
```

## Timing Summary

- Total execution time: `154366 ms` (`154.366 s`, about `2.57 min`)
- Extract task count: `25`
- Extract average duration: `4984 ms`
- Extract minimum duration: `3910 ms`
- Extract maximum duration: `6123 ms`
- Aggregate analyze duration: `14902 ms`
- Final synthesize duration: `14847 ms`

## Concurrency Reading

From this specific log, the extract tasks appear to have executed **serially**, not in parallel.

Evidence:

- Each `extract_chunk_xxxx started` line is followed by its own `succeeded` line
- Only after that does the next extract task start
- There are no overlapping `started` lines for multiple extract tasks before a prior one finishes

Observed pattern:

```text
extract_chunk_0001 started
extract_chunk_0001 succeeded
extract_chunk_0002 started
extract_chunk_0002 succeeded
...
extract_chunk_0025 succeeded
analyze_aggregated_chunk_evidence started
analyze_aggregated_chunk_evidence succeeded
synthesize_full_document_review started
synthesize_full_document_review succeeded
```

So the DAG dependency shape allows a fan-out of chunk extract tasks, but this run does not show parallel execution at the task runtime layer.

## Interpretation

This was a clean success run with no retries, no failures, and no skipped tasks.

The main practical observations are:

- The HYG PDF is not a tiny smoke sample in the current extraction + chunking setup.
- It expands into `25` chunks, which makes it a medium-weight manual regression sample.
- Most of the wall-clock time comes from the repeated extract stage.
- If faster turnaround is needed, a smaller PDF or a shorter extracted text sample would be better.

## Recommended Use

Use this sample for:

- validating `/investment-document-review-file`
- checking end-to-end review flow stability
- observing To-Do plan generation and completion logging
- regression testing after gateway / flow changes

Do not treat it as the lightest possible smoke test under the current chunking settings.
