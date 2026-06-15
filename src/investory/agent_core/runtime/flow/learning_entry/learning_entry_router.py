from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)
from investory.agent_core.runtime.message_builder import build_prompt_messages

if TYPE_CHECKING:
    from investory.agent_core.runtime.request_runner import RequestRunner


LEARNING_ENTRY_ROUTER_PROMPT_FILE = "learning_entry_router.md"


class LearningEntryRoute(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    FINANCE_QA = "finance_qa"
    LEARNING_MATERIAL_SUMMARY = "learning_material_summary"
    INSTRUMENT_BRIEF = "instrument_brief"
    GENERAL_LEARNING_CLARIFICATION = "general_learning_clarification"


class LearningEntryRouteDecision(BaseModel):
    route: LearningEntryRoute
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    missing_fields: list[str] = Field(default_factory=list)


class LearningEntryRouter(Protocol):
    def route(self, payload: dict[str, Any]) -> LearningEntryRouteDecision:
        """Return a structured routing decision for unresolved learning input."""


ROUTE_TO_CANDIDATE_TASK_TYPE = {
    LearningEntryRoute.FINANCE_QA: LearningEntryCandidateTaskType.QA,
    LearningEntryRoute.LEARNING_MATERIAL_SUMMARY: (
        LearningEntryCandidateTaskType.SUMMARY
    ),
    LearningEntryRoute.INSTRUMENT_BRIEF: LearningEntryCandidateTaskType.BRIEF,
}


def candidate_task_type_for_route(
    route: LearningEntryRoute,
) -> LearningEntryCandidateTaskType | None:
    return ROUTE_TO_CANDIDATE_TASK_TYPE.get(route)


class LearningEntryLLMRouter:
    def __init__(self, runner: "RequestRunner | None" = None) -> None:
        if runner is None:
            from investory.agent_core.runtime.request_runner import RequestRunner

            runner = RequestRunner()
        self.runner = runner

    def route(self, payload: dict[str, Any]) -> LearningEntryRouteDecision:
        messages = build_prompt_messages(
            "flows",
            LEARNING_ENTRY_ROUTER_PROMPT_FILE,
            payload,
        )

        return self.runner.run(messages, LearningEntryRouteDecision)
