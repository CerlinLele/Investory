from pydantic import BaseModel, Field


class FinanceQAInput(BaseModel):
    material_text: str = Field(
        description="Financial article, fund description, or investment learning material."
    )
    question: str = Field(
        description="Investment or personal finance question the user wants to understand."
    )


class FinanceQAResult(BaseModel):
    answer: str = Field(description="Concise answer to the user's question.")
    concept_explanation: str = Field(
        description="Learner-friendly explanation of the relevant financial concept."
    )
    evidence: list[str] = Field(
        description="Supporting points grounded in the provided material."
    )
    common_misunderstandings: list[str] = Field(
        description="Common misunderstandings related to the topic."
    )
    risk_notice: str = Field(
        description="Risk notice clarifying that the response is not investment advice."
    )
    uncertainty: str = Field(
        description="Explanation of uncertainty or information gaps in the answer."
    )
