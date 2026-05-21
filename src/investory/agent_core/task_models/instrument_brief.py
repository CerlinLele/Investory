from pydantic import BaseModel, Field


class InstrumentBriefInput(BaseModel):
    instrument_name_or_code: str = Field(
        description="Name or ticker/code of the investment instrument to study."
    )
    source_material: str = Field(
        description=(
            "User-provided fund description, ETF factsheet, news, research excerpt, "
            "or other material used as the only source for the brief."
        )
    )


class InstrumentKeyFact(BaseModel):
    label: str = Field(description="Name of the extracted fact.")
    value: str = Field(description="Value of the extracted fact grounded in the source.")


class InstrumentBriefResult(BaseModel):
    instrument_name_or_code: str = Field(
        description="Name or ticker/code of the investment instrument."
    )
    instrument_type: str = Field(
        description="Instrument type, such as ETF, fund, stock, bond, REITs, or unknown."
    )
    overview: str = Field(description="Learner-friendly overview of the instrument.")
    key_facts: list[InstrumentKeyFact] = Field(
        description="Structured facts extracted from the provided source material."
    )
    learning_points: list[str] = Field(
        description="Concepts a learner should pay attention to."
    )
    risk_notes: list[str] = Field(
        description="Risks, limitations, or common misunderstandings shown by the material."
    )
    follow_up_questions: list[str] = Field(
        description="Useful follow-up questions for continued learning."
    )
    risk_notice: str = Field(
        description="Notice clarifying that the brief is not investment advice."
    )
    uncertainty: str = Field(
        description="Information gaps or uncertainty in the provided material."
    )
