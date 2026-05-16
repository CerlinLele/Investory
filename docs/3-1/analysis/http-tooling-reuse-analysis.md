# HTTP Tooling Reuse Analysis Baseline (Step 1)

- Plan: `docs/3-1/plans/http-tooling-reuse-plan.md`
- Step: 1 - Establish duplicate-logic baseline (read-only)
- Date: 2026-05-16
- Scope files:
  - `src/investory/agent_core/tools/instrument_profile.py`
  - `src/investory/agent_core/tools/web_search.py`

## 1) Duplicate logic comparison (with code anchors)

| Shared concern | `instrument_profile.py` anchor | `web_search.py` anchor | Baseline note |
|---|---|---|---|
| Error policy map (`ErrorType -> retryable`) | `instrument_profile.py:15-38` | `web_search.py:14-37` | Literal keys and retryable booleans are aligned. |
| Generic error ToolResult builder | `instrument_profile.py:90-97` | `web_search.py:51-58` | Same structure; only tool-specific name/message differ. |
| Failure fold from `last_error` | `instrument_profile.py:68-87` | `web_search.py:106-122` | Both do `last_error=None -> not_found`, else normalize against policy. |
| Candidate loop skeleton | `instrument_profile.py:112-133` | `web_search.py:138-160` | Ordered candidate iteration with `guarded_get`, elapsed time, host parse, and continue-on-failure. |
| `guarded_get` invocation shape | `instrument_profile.py:114-119` | `web_search.py:140-145` | Same call contract: `url/timeout/allowed_hosts/user_agent`. |
| Attempt logging on HTTP failure | `instrument_profile.py:124-130` | `web_search.py:151-157` | Same `log_http_attempt(... success=False, error_type=<attempt error>)` pattern. |
| Parse-failure logging + synthesized `parse_error` | `instrument_profile.py:137-150` | `web_search.py:175-188` | Both log parse failure and assign synthesized `parse_error` into `last_error`. |
| Success logging on usable response | `instrument_profile.py:151-157` | `web_search.py:161-167` | Same `success=True, error_type=None` logging shape. |
| Final all-failed fallback | `instrument_profile.py:170` | `web_search.py:193-194` | Both converge to failure-fold when no usable result exists. |

## 2) Extract vs keep classification

### Extract to shared runner

1. Ordered candidate execution skeleton (`loop/continue/break`).
- Anchors: `instrument_profile.py:112-133`, `web_search.py:138-160`
2. `guarded_get` execution with timeout/allowlist/user-agent pass-through and elapsed-time calculation.
- Anchors: `instrument_profile.py:114-121`, `web_search.py:140-147`
3. HTTP failure logging and `last_error` update.
- Anchors: `instrument_profile.py:124-132`, `web_search.py:151-159`
4. Parse failure logging and parse-error convergence.
- Anchors: `instrument_profile.py:137-150`, `web_search.py:175-188`
5. Success attempt logging.
- Anchors: `instrument_profile.py:151-157`, `web_search.py:161-167`
6. `last_error -> ToolResult` convergence policy (allowing tool-specific fallback message text).
- Anchors: `instrument_profile.py:68-87`, `web_search.py:106-122`

### Keep at tool layer

1. Candidate source/provider construction.
- Anchors: `instrument_profile.py:60-65`, `web_search.py:79-92`
2. Parse rules and parse-success thresholds.
- Anchors: `instrument_profile.py:41-49`, `instrument_profile.py:136`; `web_search.py:61-77`, `web_search.py:174`
3. Success payload shape.
- Anchors: `instrument_profile.py:159-168`, `web_search.py:196-204`
4. Input-validation messages.
- Anchors: `instrument_profile.py:101-106`, `web_search.py:126-131`

## 3) Behavior-invariance checklist (must be locked by tests before migration)

1. Input error semantics must stay the same.
- `instrument_profile`: empty input -> `invalid_input`, message `instrument_name_or_code is required.` (`instrument_profile.py:101-106`)
- `web_search`: empty input -> `invalid_input`, message `query is required.` (`web_search.py:126-131`)

2. Fallback order semantics must stay the same.
- `instrument_profile` must preserve `_build_candidate_sources` order and returned attempted URL list in `sources`. (`instrument_profile.py:108-109`, `instrument_profile.py:122`, `instrument_profile.py:165`)
- `web_search` must preserve `_provider_candidates` order and returned attempted provider list in `provider_attempt_order`. (`web_search.py:138`, `web_search.py:148`, `web_search.py:202`)

3. Failure convergence semantics must stay the same.
- If no usable result exists:
  - `last_error is None` -> `not_found`
  - Else normalize `last_error.error_type`, fallback to `network_error` when unknown
  - `retryable` from policy map
- Anchors: `instrument_profile.py:71-87`, `web_search.py:107-122`

4. Parse-error semantics must stay the same.
- `instrument_profile`: extracted content length `< MIN_SOURCE_MATERIAL_CHARS` -> parse_error. (`instrument_profile.py:136-150`)
- `web_search`: empty snippet -> parse_error. (`web_search.py:174-188`)

5. Logging semantics must stay the same.
- Every attempt must emit `log_http_attempt` with stable keys: `tool_name/host/elapsed_ms/success/error_type`.
- Anchors: `instrument_profile.py:124-130`, `instrument_profile.py:137-143`, `instrument_profile.py:151-157`; `web_search.py:151-157`, `web_search.py:175-181`, `web_search.py:161-167`

## 4) Step 1 conclusion

- Both tools are highly duplicated at the HTTP candidate-execution skeleton level and are good candidates for shared-runner extraction.
- Tool-specific logic is concentrated in candidate construction, parse thresholds, and success payload shape; those should remain local.
- Step 2 should first lock the behavior-invariance checklist with tests, then proceed to extraction.
