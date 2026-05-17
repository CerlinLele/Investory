# HTTP Tooling Reuse Worklog

## 2026-05-16 - Step 1 Completed (Establish duplicate-logic baseline)

- Timestamp: 2026-05-16 (Australia/Sydney)
- Plan step: `Step 1 - Establish duplicate-logic baseline (read-only)`
- Actions:
  - Read baseline sources with line numbers:
    - `src/investory/agent_core/tools/instrument_profile.py`
    - `src/investory/agent_core/tools/web_search.py`
  - Built duplicate-logic comparison table and extract/keep classification.
  - Wrote behavior-invariance checklist with code anchors.
- Files touched:
  - `docs/3-1/analysis/http-tooling-reuse-analysis.md` (created)
  - `docs/3-1/worklog/http-tooling-reuse-worklog.md` (created)
- Result:
  - Step 1 deliverable completed and saved.
  - No code under `src/` changed.

## 2026-05-17 - Step 2 Completed (Lock behavior with tests)

- Timestamp: 2026-05-17 (Australia/Sydney)
- Plan step: `Step 2 - Lock behavior with tests before extraction`
- Actions:
  - Reviewed existing tool tests to avoid duplicate scenarios.
  - Added web_search behavior-lock tests for:
    - fallback semantics: first provider fails, next provider succeeds, attempt order preserved.
    - parse_error semantics: successful HTTP response with empty extracted content converges to `parse_error`.
  - Ran focused baseline suite for both tools.
- Files touched:
  - `tests/test_web_search_tool.py` (updated)
  - `docs/3-1/worklog/http-tooling-reuse-worklog.md` (updated)
- Test baseline result:
  - Command: `pytest -q tests/test_web_search_tool.py tests/test_instrument_profile_tool.py`
  - Result: `19 passed in 0.16s`
- Result:
  - Step 2 behavior lock completed for fallback ordering, failure convergence, and parse_error semantics.

## 2026-05-17 - Step 3 Completed (Introduce shared execution skeleton)

- Timestamp: 2026-05-17 (Australia/Sydney)
- Plan step: `Step 3 - Introduce shared HTTP candidate runner (no behavior change)`
- Actions:
  - Added shared runner module `http_runner.py` for ordered candidate execution, guarded HTTP fetch, attempt logging, parse-failure convergence, and last-error tracking.
  - Added unit tests for shared runner fallback and parse-error convergence behavior.
  - Ran focused regression suite for shared runner + both existing tool test files.
- Files touched:
  - `src/investory/agent_core/tools/http_runner.py` (created)
  - `tests/test_http_runner.py` (created)
  - `docs/3-1/worklog/http-tooling-reuse-worklog.md` (updated)
- Test baseline result:
  - Command: `pytest -q tests/test_http_runner.py tests/test_web_search_tool.py tests/test_instrument_profile_tool.py`
  - Result: `21 passed in 0.17s`
- Result:
  - Shared execution skeleton introduced and verified without changing tool-level business payload code yet.

## 2026-05-17 - Step 4 Completed (Migrate web_search to shared runner)

- Timestamp: 2026-05-17 (Australia/Sydney)
- Plan step: `Step 4 - Migrate web_search to shared layer`
- Actions:
  - Refactored `web_search.search_web` to reuse `run_guarded_candidates` from `http_runner`.
  - Preserved tool-layer payload shape: `query`, `results`, `provider_attempt_order`.
  - Preserved existing failure fold semantics via `_build_failure_result(last_error)`.
  - Kept `guarded_get` injection point in `web_search` to maintain existing test monkeypatch contract.
- Files touched:
  - `src/investory/agent_core/tools/web_search.py` (updated)
  - `docs/3-1/worklog/http-tooling-reuse-worklog.md` (updated)
- Test baseline result:
  - Commands:
    - `pytest -q tests/test_web_search_tool.py`
    - `pytest -q tests/test_http_runner.py tests/test_instrument_profile_tool.py`
  - Result: `6 passed` + `15 passed` (total `21 passed`)
- Result:
  - `web_search` now reuses shared HTTP execution skeleton without changing externally observable result schema.

## 2026-05-17 - Step 5 Completed (Migrate instrument_profile to shared runner)

- Timestamp: 2026-05-17 (Australia/Sydney)
- Plan step: `Step 5 - Migrate instrument_profile to shared layer`
- Actions:
  - Refactored `fetch_instrument_profile` to reuse `run_guarded_candidates` from `http_runner`.
  - Converted candidate source list to `Candidate` objects while preserving URL attempt order in returned `sources`.
  - Preserved parse-error threshold logic and failure fold semantics.
  - Kept `guarded_get` injection point in `instrument_profile` to maintain existing test monkeypatch contract.
- Files touched:
  - `src/investory/agent_core/tools/instrument_profile.py` (updated)
  - `docs/3-1/worklog/http-tooling-reuse-worklog.md` (updated)
- Test baseline result:
  - Commands:
    - `pytest -q tests/test_instrument_profile_tool.py`
    - `pytest -q tests/test_web_search_tool.py tests/test_http_runner.py`
  - Result: `13 passed` + `8 passed` (total `21 passed`)
- Result:
  - `instrument_profile` now reuses shared HTTP execution skeleton without changing externally observable result schema.
