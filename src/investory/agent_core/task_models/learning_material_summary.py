from pydantic import BaseModel, Field


class LearningMaterialSummaryInput(BaseModel):
    material_text: str = Field(
        description="Financial article, fund description, or investment learning material."
    )


class LearningTodo(BaseModel):
    title: str = Field(description="Title of the suggested follow-up learning item.")
    reason: str = Field(description="Reason this item is recommended for further study.")


class LearningMaterialSummaryResult(BaseModel):
    summary: str = Field(description="Core summary of the provided material.")
    key_concepts: list[str] = Field(
        description="Key financial concepts mentioned in the material."
    )
    key_takeaways: list[str] = Field(
        description="Important conclusions or lessons from the material."
    )
    risks: list[str] = Field(
        description="Risk reminders or common misunderstandings from the material."
    )
    todos: list[LearningTodo] = Field(
        description="Suggested follow-up learning tasks."
    )
    uncertainty: str = Field(
        description="Information gaps or uncertainty found in the material."
    )
