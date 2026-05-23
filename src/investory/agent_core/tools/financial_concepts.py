from pydantic import BaseModel, Field

from investory.agent_core.tools.contracts import ToolSource


class FinancialConceptInput(BaseModel):
    concept: str = Field(description="Financial concept to explain.")


class FinancialConceptOutput(BaseModel):
    concept: str
    definition: str
    learning_points: list[str]
    source: ToolSource
    uncertainty: list[str] = Field(default_factory=list)


_CONCEPTS: dict[str, dict[str, list[str] | str]] = {
    "etf": {
        "definition": (
            "An exchange-traded fund is an investment fund traded on an exchange "
            "that usually represents a basket of securities."
        ),
        "learning_points": [
            "ETF prices can move during market hours.",
            "Expense ratio, tracking method, and underlying exposure affect outcomes.",
            "Diversification reduces single-security concentration but does not remove market risk.",
        ],
    },
    "expense ratio": {
        "definition": (
            "Expense ratio is the recurring fund cost expressed as a percentage "
            "of assets each year."
        ),
        "learning_points": [
            "Lower costs can reduce drag on long-term returns.",
            "Costs should be compared alongside index, exposure, and fund structure.",
        ],
    },
    "diversification": {
        "definition": (
            "Diversification means spreading exposure across multiple assets, sectors, "
            "or regions to reduce dependence on one outcome."
        ),
        "learning_points": [
            "Diversification can reduce idiosyncratic risk.",
            "Diversified portfolios can still lose value during broad market declines.",
        ],
    },
}


class FinancialConceptTool:
    name = "lookup_financial_concept"
    description = "Explains a financial concept for investment learning."
    input_model = FinancialConceptInput
    output_model = FinancialConceptOutput

    def run(self, payload: BaseModel) -> BaseModel:
        request = self.input_model.model_validate(payload)
        normalized = request.concept.strip().lower()
        concept = _CONCEPTS.get(normalized)

        if concept is None:
            return self.output_model(
                concept=request.concept,
                definition="No mock definition is available for this concept.",
                learning_points=[],
                source=ToolSource(provider="mock_financial_concepts", as_of="2026-05-24"),
                uncertainty=[
                    "The mock concept catalog only contains a small fixed set of entries."
                ],
            )

        return self.output_model(
            concept=request.concept,
            definition=str(concept["definition"]),
            learning_points=list(concept["learning_points"]),
            source=ToolSource(provider="mock_financial_concepts", as_of="2026-05-24"),
            uncertainty=[],
        )
