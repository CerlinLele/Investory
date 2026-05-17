from investory.agent_core.tools.http_runner import (
    Candidate,
    ParseOutcome,
    run_guarded_candidates,
)
from investory.agent_core.tools.net_guard import GuardedHttpResult


def test_run_guarded_candidates_fallbacks_to_next_candidate_then_succeeds():
    calls = {"count": 0}
    logs: list[dict[str, object]] = []

    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return GuardedHttpResult(
                ok=False,
                error_type="timeout",
                error_message="timeout",
                retryable=True,
            )
        return GuardedHttpResult(ok=True, status_code=200, text="usable html text")

    def _fake_log_attempt(**kwargs):
        logs.append(kwargs)

    def _parse_success(candidate, text):
        return ParseOutcome(ok=True, item={"candidate_id": candidate.id, "text": text})

    outcome = run_guarded_candidates(
        tool_name="test_tool",
        candidates=[
            Candidate(id="provider_a", url="https://www.example.com/a"),
            Candidate(id="provider_b", url="https://www.example.com/b"),
        ],
        timeout_seconds=8,
        allowed_hosts=("www.example.com",),
        user_agent="Test/1.0",
        parse_success=_parse_success,
        max_successes=1,
        guarded_get_fn=_fake_guarded_get,
        log_attempt_fn=_fake_log_attempt,
    )

    assert outcome.attempt_order == ["provider_a", "provider_b"]
    assert len(outcome.items) == 1
    assert outcome.items[0]["candidate_id"] == "provider_b"
    assert outcome.last_error is not None
    assert outcome.last_error.error_type == "timeout"
    assert len(logs) == 2
    assert logs[0]["success"] is False
    assert logs[0]["error_type"] == "timeout"
    assert logs[1]["success"] is True
    assert logs[1]["error_type"] is None


def test_run_guarded_candidates_returns_parse_error_when_all_parse_fail():
    logs: list[dict[str, object]] = []

    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(ok=True, status_code=200, text="<html></html>")

    def _fake_log_attempt(**kwargs):
        logs.append(kwargs)

    def _parse_success(candidate, text):
        return ParseOutcome(
            ok=False,
            error_type="parse_error",
            error_message=f"candidate {candidate.id} empty content",
        )

    outcome = run_guarded_candidates(
        tool_name="test_tool",
        candidates=[
            Candidate(id="first", url="https://www.example.com/first"),
            Candidate(id="second", url="https://www.example.com/second"),
        ],
        timeout_seconds=8,
        allowed_hosts=("www.example.com",),
        user_agent="Test/1.0",
        parse_success=_parse_success,
        guarded_get_fn=_fake_guarded_get,
        log_attempt_fn=_fake_log_attempt,
    )

    assert outcome.items == []
    assert outcome.attempt_order == ["first", "second"]
    assert outcome.last_error is not None
    assert outcome.last_error.error_type == "parse_error"
    assert outcome.last_error.retryable is False
    assert "candidate second empty content" in (outcome.last_error.error_message or "")
    assert len(logs) == 2
    assert logs[0]["success"] is False
    assert logs[0]["error_type"] == "parse_error"
