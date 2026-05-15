from investory.agent_core.tools.instrument_profile import (
    ALLOWED_HOSTS,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_SOURCE_MATERIAL_CHARS,
    fetch_instrument_profile,
)


def test_fetch_instrument_profile_returns_mock_result_for_valid_code():
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.tool_name == "fetch_instrument_profile"
    assert result.data is not None
    assert result.data["instrument_name_or_code"] == "VTI"
    assert "source_material" in result.data
    assert isinstance(result.data["sources"], list)
    assert len(result.data["sources"]) >= 1
    assert isinstance(result.data["as_of"], str)


def test_fetch_instrument_profile_rejects_empty_code():
    result = fetch_instrument_profile("  ")

    assert result.ok is False
    assert result.error_type == "invalid_input"
    assert result.error_message == "instrument_name_or_code is required."
    assert result.retryable is False


def test_fetch_instrument_profile_freezes_https_allowlist_boundary():
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.data is not None
    assert all(url.startswith("https://") for url in result.data["sources"])
    assert all(any(host in url for host in ALLOWED_HOSTS) for url in result.data["sources"])


def test_fetch_instrument_profile_source_material_has_max_length():
    result = fetch_instrument_profile("vti")

    assert result.ok is True
    assert result.data is not None
    assert len(result.data["source_material"]) <= MAX_SOURCE_MATERIAL_CHARS


def test_fetch_instrument_profile_has_default_timeout_constant():
    assert DEFAULT_TIMEOUT_SECONDS > 0
