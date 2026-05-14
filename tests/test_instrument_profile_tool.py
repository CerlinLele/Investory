from investory.agent_core.tools.instrument_profile import fetch_instrument_profile


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
