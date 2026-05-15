from investory.agent_core.tools.instrument_profile import (
    ALLOWED_HOSTS,
    DEFAULT_TIMEOUT_SECONDS,
    ERROR_RETRYABLE_POLICY,
    MAX_SOURCE_MATERIAL_CHARS,
    _extract_profile_text,
    fetch_instrument_profile,
)
from investory.agent_core.tools.net_guard import GuardedHttpResult


def test_fetch_instrument_profile_returns_first_success_result(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=True,
            status_code=200,
            text="VTI profile summary with fund strategy and holdings details.",
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.tool_name == "fetch_instrument_profile"
    assert result.data is not None
    assert result.data["instrument_name_or_code"] == "VTI"
    assert "Instrument: VTI" in result.data["source_material"]
    assert "Profile Summary:" in result.data["source_material"]
    assert isinstance(result.data["sources"], list)
    assert len(result.data["sources"]) >= 1
    assert isinstance(result.data["as_of"], str)


def test_fetch_instrument_profile_rejects_empty_code():
    result = fetch_instrument_profile("  ")

    assert result.ok is False
    assert result.error_type == "invalid_input"
    assert result.error_message == "instrument_name_or_code is required."
    assert result.retryable is False


def test_fetch_instrument_profile_freezes_https_allowlist_boundary(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        assert url.startswith("https://")
        assert allowed_hosts == ALLOWED_HOSTS
        return GuardedHttpResult(
            ok=True,
            status_code=200,
            text="Enough descriptive content for pass-through extraction.",
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.data is not None
    assert all(url.startswith("https://") for url in result.data["sources"])
    assert all(any(host in url for host in ALLOWED_HOSTS) for url in result.data["sources"])


def test_fetch_instrument_profile_source_material_has_max_length(monkeypatch):
    long_text = "x" * (MAX_SOURCE_MATERIAL_CHARS + 20)

    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(ok=True, status_code=200, text=long_text)

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.data is not None
    assert len(result.data["source_material"]) <= MAX_SOURCE_MATERIAL_CHARS


def test_fetch_instrument_profile_has_default_timeout_constant():
    assert DEFAULT_TIMEOUT_SECONDS > 0


def test_fetch_instrument_profile_fallbacks_to_next_source(monkeypatch):
    calls = {"count": 0}

    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return GuardedHttpResult(
                ok=False,
                error_type="timeout",
                error_message="timed out",
                retryable=True,
            )
        return GuardedHttpResult(
            ok=True,
            status_code=200,
            text="fallback success with sufficient profile details for summary output.",
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.data is not None
    assert "fallback success" in result.data["source_material"]
    assert len(result.data["sources"]) == 2


def test_fetch_instrument_profile_returns_error_when_all_sources_fail(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="network_error",
            error_message="upstream unavailable",
            retryable=True,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is False
    assert result.error_type == "network_error"
    assert result.error_message == "upstream unavailable"
    assert result.retryable is True


def test_fetch_instrument_profile_enforces_retryable_by_error_policy(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="timeout",
            error_message="request timeout",
            retryable=False,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is False
    assert result.error_type == "timeout"
    assert result.retryable == ERROR_RETRYABLE_POLICY["timeout"]


def test_fetch_instrument_profile_normalizes_unknown_error_type(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(
            ok=False,
            error_type="upstream_gateway",
            error_message="gateway issue",
            retryable=False,
        )

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is False
    assert result.error_type == "network_error"
    assert result.retryable == ERROR_RETRYABLE_POLICY["network_error"]


def test_extract_profile_text_removes_html_and_normalizes_space():
    raw = "<html><body><h1>VTI</h1><script>x=1</script><p>  ETF&nbsp;summary </p></body></html>"
    extracted = _extract_profile_text(raw)
    assert "<h1>" not in extracted
    assert "script" not in extracted.lower()
    assert extracted == "VTI ETF summary"


def test_fetch_instrument_profile_returns_parse_error_when_content_too_short(monkeypatch):
    def _fake_guarded_get(url, *, timeout, allowed_hosts, user_agent=None):
        return GuardedHttpResult(ok=True, status_code=200, text="too short")

    monkeypatch.setattr(
        "investory.agent_core.tools.instrument_profile.guarded_get",
        _fake_guarded_get,
    )
    result = fetch_instrument_profile("vti")

    assert result.ok is False
    assert result.error_type == "parse_error"
    assert result.retryable is False
