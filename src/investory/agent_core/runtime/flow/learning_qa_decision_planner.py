from typing import Any

from investory.agent_core.contracts.action_contract import (
    ASK_MISSING_FIELDS,
    RUN_TASK_MODEL,
    TaskDecision,
)
from investory.agent_core.contracts.action_decision import build_ask_missing_fields_action
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.input_requirements import get_missing_required_fields


class LearningQaDecisionPlanner:
    def decide(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskDecision:
        missing_fields = get_missing_required_fields(spec, payload)
        if missing_fields:
            action = build_ask_missing_fields_action(
                task_name=spec.name,
                missing_fields=missing_fields,
            )
            return TaskDecision(
                action=ASK_MISSING_FIELDS,
                task_name=spec.name,
                reason=action.reason,
                params={"missing_fields": action.missing_fields},
                user_message=action.user_message,
            )

        return TaskDecision(
            action=RUN_TASK_MODEL,
            task_name=spec.name,
            reason=f"The request contains all required input fields for {spec.name}.",
            params={"payload": dict(payload)},
        )


def build_task_decision(
    spec: TaskSpec,
    payload: dict[str, Any],
    planner: LearningQaDecisionPlanner | None = None,
) -> TaskDecision:
    resolved_planner = planner or LearningQaDecisionPlanner()
    return resolved_planner.decide(spec, payload)


# Backward-compatible alias during naming migration.
DecisionPlanner = LearningQaDecisionPlanner
