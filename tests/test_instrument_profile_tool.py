from investory.agent_core.tools import InstrumentProfileInput, InstrumentProfileTool


def test_instrument_profile_tool_returns_known_mock_profile():
    tool = InstrumentProfileTool()

    result = tool.run(InstrumentProfileInput(instrument_name_or_code="VTI"))

    dumped = result.model_dump()
    assert dumped["instrument_name_or_code"] == "VTI"
    assert dumped["resolved_name"] == "Vanguard Total Stock Market ETF"
    assert dumped["instrument_type"] == "ETF"
    assert "educational workflow testing only" in dumped["source_material"]
    assert dumped["facts"]
    assert dumped["source"]["provider"] == "mock_instrument_profiles"
    assert dumped["source"]["as_of"] == "2026-05-24"
    assert dumped["uncertainty"] == []


def test_instrument_profile_tool_returns_unknown_profile_with_uncertainty():
    tool = InstrumentProfileTool()

    result = tool.run({"instrument_name_or_code": "XYZ"})

    assert result.resolved_name == "XYZ"
    assert result.instrument_type == "unknown"
    assert result.uncertainty
    assert result.source.provider == "mock_instrument_profiles"


def test_instrument_profile_tool_output_is_advice_neutral():
    tool = InstrumentProfileTool()

    result_text = str(tool.run({"instrument_name_or_code": "VOO"}).model_dump()).lower()

    for restricted_term in ["buy", "sell", "hold", "suitability", "allocation"]:
        assert restricted_term not in result_text
