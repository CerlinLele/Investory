from pydantic import BaseModel, Field

from investory.agent_core.tools.contracts import ToolSource


class InstrumentProfileInput(BaseModel):
    instrument_name_or_code: str = Field(
        description="Name or ticker/code of the investment instrument to study."
    )


class InstrumentProfileOutput(BaseModel):
    instrument_name_or_code: str
    resolved_name: str
    instrument_type: str
    source_material: str
    facts: list[dict[str, str]]
    source: ToolSource
    uncertainty: list[str] = Field(default_factory=list)


_PROFILES: dict[str, dict[str, object]] = {
    "VTI": {
        "resolved_name": "Vanguard Total Stock Market ETF",
        "instrument_type": "ETF",
        "facts": [
            {"label": "Exposure", "value": "Broad U.S. equity market"},
            {"label": "Structure", "value": "Exchange-traded fund"},
            {"label": "Learning focus", "value": "Market-wide equity exposure and index tracking"},
        ],
    },
    "VOO": {
        "resolved_name": "Vanguard S&P 500 ETF",
        "instrument_type": "ETF",
        "facts": [
            {"label": "Exposure", "value": "Large-cap U.S. equities represented by the S&P 500"},
            {"label": "Structure", "value": "Exchange-traded fund"},
            {"label": "Learning focus", "value": "Index tracking, concentration, and fund costs"},
        ],
    },
}


def _build_source_material(
    *, resolved_name: str, instrument_type: str, facts: list[dict[str, str]]
) -> str:
    fact_text = "; ".join(f"{fact['label']}: {fact['value']}" for fact in facts)
    return (
        f"{resolved_name} is represented in this mock profile as an {instrument_type}. "
        f"Key learning facts: {fact_text}. "
        "This mock profile is for educational workflow testing only and does not "
        "provide investment advice."
    )


class InstrumentProfileTool:
    name = "lookup_instrument_profile"
    description = "Returns a stable mock profile for an investment instrument."
    input_model = InstrumentProfileInput
    output_model = InstrumentProfileOutput

    def run(self, payload: BaseModel) -> BaseModel:
        request = self.input_model.model_validate(payload)
        raw_code = request.instrument_name_or_code.strip()
        normalized = raw_code.upper()
        profile = _PROFILES.get(normalized)

        if profile is None:
            facts = [
                {"label": "Instrument code", "value": raw_code},
                {"label": "Profile status", "value": "No matching mock profile"},
            ]
            return self.output_model(
                instrument_name_or_code=request.instrument_name_or_code,
                resolved_name=raw_code,
                instrument_type="unknown",
                source_material=_build_source_material(
                    resolved_name=raw_code,
                    instrument_type="unknown instrument",
                    facts=facts,
                ),
                facts=facts,
                source=ToolSource(provider="mock_instrument_profiles", as_of="2026-05-24"),
                uncertainty=[
                    "The mock instrument catalog only includes a small fixed set of symbols."
                ],
            )

        facts = list(profile["facts"])
        resolved_name = str(profile["resolved_name"])
        instrument_type = str(profile["instrument_type"])
        return self.output_model(
            instrument_name_or_code=request.instrument_name_or_code,
            resolved_name=resolved_name,
            instrument_type=instrument_type,
            source_material=_build_source_material(
                resolved_name=resolved_name,
                instrument_type=instrument_type,
                facts=facts,
            ),
            facts=facts,
            source=ToolSource(provider="mock_instrument_profiles", as_of="2026-05-24"),
            uncertainty=[],
        )
