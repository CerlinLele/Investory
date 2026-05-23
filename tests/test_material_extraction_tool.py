from investory.agent_core.tools import MaterialExtractionInput, MaterialExtractionTool


def test_material_extraction_tool_extracts_sentences_and_concepts():
    tool = MaterialExtractionTool()

    result = tool.run(
        MaterialExtractionInput(
            material_text=(
                "The ETF tracks a broad market index. "
                "Its expense ratio is an annual fund cost. "
                "Investors should understand market risk."
            )
        )
    )

    dumped = result.model_dump()
    assert [fact["label"] for fact in dumped["facts"]] == [
        "Statement 1",
        "Statement 2",
        "Statement 3",
    ]
    assert "ETF" in dumped["key_concepts"]
    assert "Expense ratio" in dumped["key_concepts"]
    assert "Market risk" in dumped["key_concepts"]
    assert dumped["source"]["provider"] == "user_material"
    assert dumped["source"]["as_of"] == "2026-05-24"
    assert dumped["uncertainty"] == []


def test_material_extraction_tool_reports_uncertainty_for_empty_material():
    tool = MaterialExtractionTool()

    result = tool.run({"material_text": ""})

    assert result.facts == []
    assert result.key_concepts == []
    assert len(result.uncertainty) == 2


def test_material_extraction_tool_output_is_advice_neutral():
    tool = MaterialExtractionTool()

    result_text = str(
        tool.run({"material_text": "The ETF tracks an index and has market risk."}).model_dump()
    ).lower()

    for restricted_term in ["buy", "sell", "hold", "suitability", "allocation"]:
        assert restricted_term not in result_text
