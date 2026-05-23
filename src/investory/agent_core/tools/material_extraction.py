import re

from pydantic import BaseModel, Field

from investory.agent_core.tools.contracts import ToolSource


class MaterialExtractionInput(BaseModel):
    material_text: str = Field(
        description="Financial article, fund description, or investment learning material."
    )


class MaterialFact(BaseModel):
    label: str
    value: str


class MaterialExtractionOutput(BaseModel):
    facts: list[MaterialFact]
    key_concepts: list[str]
    source: ToolSource
    uncertainty: list[str] = Field(default_factory=list)


_CONCEPT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ETF": ("etf", "exchange-traded fund"),
    "Expense ratio": ("expense ratio", "fee", "cost"),
    "Diversification": ("diversification", "diversified", "broad market"),
    "Index tracking": ("index", "tracking"),
    "Market risk": ("risk", "volatility", "drawdown"),
}


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


class MaterialExtractionTool:
    name = "extract_learning_material_facts"
    description = "Extracts stable learning facts from provided material text."
    input_model = MaterialExtractionInput
    output_model = MaterialExtractionOutput

    def run(self, payload: BaseModel) -> BaseModel:
        request = self.input_model.model_validate(payload)
        material_text = request.material_text.strip()
        lowered = material_text.lower()
        sentences = _sentences(material_text)
        key_concepts = [
            concept
            for concept, keywords in _CONCEPT_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        ]

        facts = [
            MaterialFact(label=f"Statement {index}", value=sentence)
            for index, sentence in enumerate(sentences[:3], start=1)
        ]
        uncertainty: list[str] = []
        if not facts:
            uncertainty.append("No extractable sentences were found in the provided material.")
        if not key_concepts:
            uncertainty.append("No known mock concept keywords were detected.")

        return self.output_model(
            facts=facts,
            key_concepts=key_concepts,
            source=ToolSource(provider="user_material", as_of="2026-05-24"),
            uncertainty=uncertainty,
        )
