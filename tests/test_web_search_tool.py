from investory.agent_core.tools.net_guard import GuardedHttpResult
from investory.agent_core.tools.web_search import (
    ALLOWED_HOSTS,
    DEFAULT_TIMEOUT_SECONDS,
    ERROR_RETRYABLE_POLICY,
    search_web,
)


def test_search_web_returns_structured_results_on_success(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        assert timeout == DEFAULT_TIMEOUT_SECONDS
        assert allowed_hosts == ALLOWED_HOSTS
        return GuardedHttpResult(
            ok=True,
            status_code=200,
            text="<html><title>Mock Result</title><body>ETF research summary snippet.</body></html>",
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.web_search.guarded_get",
        _fake_guarded_get,
    )
    result = search_web("vti", top_k=1)

    assert result.ok is True
    assert result.tool_name == "web_search"
    assert result.data is not None
    assert result.data["query"] == "vti"
    assert isinstance(result.data["results"], list)
    assert len(result.data["results"]) == 1
    item = result.data["results"][0]
    assert item["title"] == "Mock Result"
    assert item["url"].startswith("https://")
    assert item["snippet"]
    assert item["source"]
    assert item["provider"]


def test_search_web_returns_timeout_error_when_providers_timeout(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="timeout",
            error_message="request timeout",
            retryable=True,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.web_search.guarded_get",
        _fake_guarded_get,
    )
    result = search_web("vti", top_k=2)

    assert result.ok is False
    assert result.error_type == "timeout"
    assert result.retryable == ERROR_RETRYABLE_POLICY["timeout"]


def test_search_web_returns_blocked_host_error(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="blocked_host",
            error_message="host blocked",
            retryable=False,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.web_search.guarded_get",
        _fake_guarded_get,
    )
    result = search_web("vti")

    assert result.ok is False
    assert result.error_type == "blocked_host"
    assert result.retryable == ERROR_RETRYABLE_POLICY["blocked_host"]


def test_search_web_returns_network_error_when_all_providers_fail(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="network_error",
            error_message="upstream unavailable",
            retryable=True,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.web_search.guarded_get",
        _fake_guarded_get,
    )
    result = search_web("vti", provider_hint="example_search")

    assert result.ok is False
    assert result.error_type == "network_error"
    assert result.retryable == ERROR_RETRYABLE_POLICY["network_error"]
    assert "upstream unavailable" in (result.error_message or "")
