from pydantic import BaseModel, Field, field_validator

from investory.agent_core.contracts.learning_entry_state import LearningEntryDecision


POLICY_ROUTE_ACTIONS = frozenset(
    {
        LearningEntryDecision.REFUSE_AND_REDIRECT,
        LearningEntryDecision.EXECUTE_LEARNING_TASK,
    }
)


class LearningEntryPolicyDecision(BaseModel):
    route_action: LearningEntryDecision = Field(
        description=(
            "Policy route for the request after missing fields have already "
            "been checked."
        )
    )
    reason: str = Field(
        description="Brief explanation for why the route action was selected."
    )

    @field_validator("route_action")
    @classmethod
    def validate_policy_route_action(
        cls,
        route_action: LearningEntryDecision,
    ) -> LearningEntryDecision:
        if route_action not in POLICY_ROUTE_ACTIONS:
            allowed = ", ".join(sorted(action.value for action in POLICY_ROUTE_ACTIONS))
            raise ValueError(f"route_action must be one of: {allowed}")
        return route_action
