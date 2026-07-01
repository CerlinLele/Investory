# HYG File Upload Test Result — Dimension-Concurrent Analyze

## Test Artifact

- Session ID: `apifox-hyg-file-upload`
- Source PDF: `data/hyg-ishares-iboxx-high-yield-corporate-bond-etf-fund-fact-sheet-en-us.pdf`
- Raw log extract: `test-results/hyg-file-upload/reflection-2026-07-01/log.md`
- Reflection summary: `test-results/hyg-file-upload/reflection-2026-07-01/summary.md`
- Prior rerun for comparison (single aggregate analyze): `test-results/hyg-file-upload/rerun-2026-06-10-after-concurrency-fix/`
- Baseline for comparison (no concurrency): `test-results/hyg-file-upload/baseline/`

## Outcome

The file upload review ran successfully from start to finish, now with the analyze stage fanned out by review dimension instead of one aggregate analyze task.

- `ok`: success from the logged task execution perspective
- `document_type`: `etf_factsheet`
- `chunk_count`: `25`
- `task_count`: `29`
- `failure_policy`: `retry_then_fail`
- `synthesis_produced`: `true`
- `reflection`: `passed=true score=0.96 rounds=1 issue_count=0`

Final completion line:

```text
investment_document_review.todo_execution.completed session_id=apifox-hyg-file-upload succeeded_count=29 failed_count=0 skipped_count=0 duration_ms=79070 synthesis_produced=true
```

## Task Breakdown

The plan contained:

- `25` extract tasks
- `3` dimension-specific analyze tasks
- `1` synthesize task

This matches the logged plan summary:

```text
chunk_count=25 task_count=29 summary=Extract lightweight evidence from every document chunk, analyze the evidence by review dimension, then synthesize the full document review.
```

The 3 analyze tasks came from `config/review_frameworks.yaml`'s `etf_factsheet.analyze_focus` list:

- `analyze_risk_disclosures_completeness`
- `analyze_historical_performance_boundary_statements`
- `analyze_cost_impact_on_long_term_returns`

This is a change from the prior rerun, where `analyze_focus` was effectively empty and the plan fell back to a single `analyze_aggregated_chunk_evidence` task (`task_count=27`).

## Timing Summary

- Total execution time: `79070 ms` (`79.070 s`, about `1.32 min`)
- Extract task count: `25`
- Extract average duration: `5496 ms`
- Extract minimum duration: `4079 ms` (`x0024`)
- Extract maximum duration: `10180 ms` (`x0008`)
- Analyze task count: `3`
- Analyze average duration: `10323 ms`
- Analyze minimum duration: `8311 ms` (`cost_impact_on_long_term_returns`)
- Analyze maximum duration: `11859 ms` (`risk_disclosures_completeness`)
- Final synthesize duration: `19891 ms`

## Concurrency Reading

From this log, both the extract stage and the analyze stage executed in parallel.

**Extract stage** (unchanged pattern, 3-slot pipeline):

```text
extract_chunk_0001 started
extract_chunk_0002 started
extract_chunk_0003 started
...
extract_chunk_0001 succeeded
extract_chunk_0004 started
...
```

**Analyze stage** (new: 3 dimension tasks start together once all extracts finish):

```text
extract_chunk_0025 succeeded            (47.317s)
analyze_risk_disclosures_completeness started
analyze_historical_performance_boundary_statements started
analyze_cost_impact_on_long_term_returns started
...
analyze_cost_impact_on_long_term_returns succeeded    (duration_ms=8311)
analyze_historical_performance_boundary_statements succeeded  (duration_ms=10800)
analyze_risk_disclosures_completeness succeeded        (duration_ms=11859)
synthesize_full_document_review started
```

Inference from the log shape:

- The extract worker pool is still a `3`-slot concurrent pipeline (unchanged from the prior rerun).
- All `3` analyze dimension tasks start within 1ms of each other, immediately after the last extract task succeeds — confirming they share the same `depends_on` (all 25 extract task ids) and run in the same dependency layer.
- The analyze stage wall-clock (`47.317s` to `59.176s`, about `11.86s`) equals the slowest single analyze dimension, not the sum of all three (`8.31s + 10.80s + 11.86s = 30.97s`) — this is direct evidence the 3 dimensions ran concurrently rather than sequentially.
- Synthesize still waits for all 3 analyze tasks to finish before starting.

## Baseline / Rerun Comparison

| Run | Total duration | Task count | Analyze shape |
|---|---|---|---|
| Baseline (no concurrency) | `154366 ms` | 27 | 1 aggregate analyze |
| Rerun 2026-06-10 (extract concurrency fix) | `70022 ms` | 27 | 1 aggregate analyze |
| This run 2026-07-01 (dimension analyze) | `79070 ms` | 29 | 3 concurrent analyze dimensions |

- Total duration increased by `9048 ms` (`+12.9%`) compared to the 2026-06-10 rerun, even though the 2 extra analyze tasks ran concurrently rather than sequentially.
- Still a `1.95x` speedup versus the original baseline.

Where the extra time went:

- Extract stage wall-clock: `47.317 s` (was `46.442 s`) — essentially unchanged, within normal LLM latency variance.
- Analyze stage wall-clock: `11.859 s` for 3 concurrent dimensions (was `9.494 s` for 1 aggregate task) — the slowest of the 3 dimension calls is slightly slower than the old single aggregate call, likely because each dimension-focused prompt still processes the full `dependency_results` payload from all 25 extracts.
- Synthesize duration: `19.891 s` (was `14.079 s`) — synthesize now consolidates 3 separate dimension analyses instead of 1, which costs it about `5.8s` more.

## Interpretation

This was a clean success run with no retries, no failures, no skipped tasks, and it passed reflection (`score=0.96`).

The dimension-concurrent analyze design works as intended architecturally:

- `_build_chunk_review_analyze_tasks()` now generates one task per `analyze_focus` entry from `config/review_frameworks.yaml`.
- All dimension tasks share the same `depends_on` (all extract task ids) and land in the same dependency layer, so the runner executes them concurrently.
- Synthesize correctly waits on all analyze dimension tasks and consolidates their `risk_findings` / `information_gaps` / `boundary_notes` into one final review.

One important trade-off:

- Splitting analyze into 3 dimensions did **not** reduce total runtime versus the single-aggregate-analyze rerun, because the added synthesize consolidation cost and the mild extra analyze latency outweighed the concurrency gain from running 3 tasks in parallel instead of 1.
- The benefit of this change is analysis **quality/specificity** (each dimension gets a focused prompt) rather than raw speed. If speed regresses further as more `analyze_focus` dimensions are added per document type, that would be worth revisiting (e.g. capping dimension count, or trimming `dependency_results` payload size per dimension).

## Recommended Use

Use this run as the new reference for:

- validating that `analyze_focus` from `config/review_frameworks.yaml` correctly fans out into concurrent analyze tasks
- checking whether analyze-stage concurrency is truly active (compare per-dimension `duration_ms` sum vs wall-clock)
- regression testing future changes to `config/review_frameworks.yaml` dimension counts
- comparing synthesize cost as a function of analyze dimension count
