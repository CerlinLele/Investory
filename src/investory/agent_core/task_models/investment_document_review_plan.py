from investory.agent_core.contracts.todo_execution import TodoExecutionPlan
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewInput,
)


class InvestmentDocumentReviewPlanInput(InvestmentDocumentReviewInput):
    """Input used to generate an investment document review To-Do plan."""


InvestmentDocumentReviewPlanResult = TodoExecutionPlan


__all__ = [
    "InvestmentDocumentReviewPlanInput",
    "InvestmentDocumentReviewPlanResult",
]
