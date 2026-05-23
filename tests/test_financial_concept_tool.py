from investory.agent_core.tools import (
    FinancialConceptInput,
    FinancialConceptTool,
    build_mock_tool_registry,
)


def test_financial_concept_tool_returns_known_concept():
    tool = FinancialConceptTool()

    result = tool.run(FinancialConceptInput(concept="ETF"))

    dumped = result.model_dump()
    assert dumped["concept"] == "ETF"
    assert "exchange-traded fund" in dumped["definition"]
    assert dumped["source"]["provider"] == "mock_financial_concepts"
    assert dumped["source"]["as_of"] == "2026-05-24"
    assert dumped["uncertainty"] == []


def test_financial_concept_tool_returns_uncertainty_for_unknown_concept():
    tool = FinancialConceptTool()

    result = tool.run({"concept": "duration gap"})

    assert result.definition == "No mock definition is available for this concept."
    assert result.learning_points == []
    assert result.uncertainty


def test_financial_concept_tool_output_is_advice_neutral():
    tool = FinancialConceptTool()

    result_text = str(tool.run({"concept": "diversification"}).model_dump()).lower()

    for restricted_term in ["buy", "sell", "hold", "suitability", "allocation"]:
        assert restricted_term not in result_text


def test_build_mock_tool_registry_includes_first_mock_tools():
    registry = build_mock_tool_registry()

    assert registry.list_names() == [
        "extract_learning_material_facts",
        "lookup_financial_concept",
        "lookup_instrument_profile",
    ]
