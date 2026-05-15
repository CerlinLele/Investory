from urllib.error import URLError

from investory.agent_core.tools import net_guard


def test_validate_url_rejects_non_https():
    result = net_guard.validate_url("http://example.com/a", allowed_hosts=("example.com",))
    assert result.ok is False
    assert result.error_type == "blocked_host"


def test_validate_url_rejects_non_allowlisted_host():
    result = net_guard.validate_url("https://evil.com/a", allowed_hosts=("example.com",))
    assert result.ok is False
    assert result.error_type == "blocked_host"


def test_validate_url_allows_https_allowlisted_host():
    result = net_guard.validate_url("https://example.com/a", allowed_hosts=("example.com",))
    assert result.ok is True


def test_guarded_get_short_circuits_blocked_host():
    result = net_guard.guarded_get(
        "https://evil.com/a",
        timeout=5,
        allowed_hosts=("example.com",),
    )
    assert result.ok is False
    assert result.error_type == "blocked_host"
    assert result.retryable is False


def test_guarded_get_normalizes_timeout(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(net_guard, "urlopen", _raise_timeout)
    result = net_guard.guarded_get(
        "https://example.com/a",
        timeout=5,
        allowed_hosts=("example.com",),
    )
    assert result.ok is False
    assert result.error_type == "timeout"
    assert result.retryable is True


def test_guarded_get_normalizes_network_error(monkeypatch):
    def _raise_url_error(*args, **kwargs):
        raise URLError("temporary failure")

    monkeypatch.setattr(net_guard, "urlopen", _raise_url_error)
    result = net_guard.guarded_get(
        "https://example.com/a",
        timeout=5,
        allowed_hosts=("example.com",),
    )
    assert result.ok is False
    assert result.error_type == "network_error"
    assert result.retryable is True
