from typing import Any

from pydantic import BaseModel

from investory.agent_core.runtime.flow.learning_entry_router import (
    LearningEntryLLMRouter,
    LearningEntryRoute,
    LearningEntryRouteDecision,
)


class FakeRunner:
    def __init__(self, result: LearningEntryRouteDecision) -> None:
        self.result = result
        self.messages: list[Any] | None = None
        self.output_model: type[BaseModel] | None = None

    def run(
        self,
        messages: list[Any],
        output_model: type[BaseModel],
    ) -> BaseModel:
        self.messages = messages
        self.output_model = output_model
        return self.result


def test_learning_entry_llm_router_uses_structured_route_decision_model() -> None:
    expected_result = LearningEntryRouteDecision(
        route=LearningEntryRoute.LEARNING_MATERIAL_SUMMARY,
        confidence=0.88,
        reason="The user asks to summarize learning material.",
    )
    runner = FakeRunner(expected_result)
    router = LearningEntryLLMRouter(runner=runner)

    result = router.route({"user_input": "Summarize the pasted ETF notes."})

    assert result is expected_result
    assert runner.output_model is LearningEntryRouteDecision
    assert runner.messages is not None
    assert "Summarize the pasted ETF notes." in runner.messages[1].content
