from typing import Any

from investory.agent_core.contracts.action_contract import TaskDecision
from investory.agent_core.contracts.action_decision import build_ask_missing_fields_action
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.input_requirements import get_missing_required_fields


class DecisionPlanner:
    def decide(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskDecision:
        missing_fields = get_missing_required_fields(spec, payload)
        if missing_fields:
            if spec.name == "instrument_brief" and missing_fields == ["source_material"]:
                instrument_name_or_code = str(payload["instrument_name_or_code"]).strip()
                return TaskDecision(
                    action="fetch_then_run_instrument_brief",
                    task_name=spec.name,
                    reason=(
                        "The request is missing source_material for instrument_brief, "
                        "so fetch profile data first and then run the task model."
                    ),
                    params={
                        "instrument_name_or_code": instrument_name_or_code,
                        "payload": dict(payload),
                    },
                )

            action = build_ask_missing_fields_action(
                task_name=spec.name,
                missing_fields=missing_fields,
            )
            return TaskDecision(
                action="ask_missing_fields",
                task_name=spec.name,
                reason=action.reason,
                params={"missing_fields": action.missing_fields},
                user_message=action.user_message,
            )

        return TaskDecision(
            action="run_task_model",
            task_name=spec.name,
            reason=f"The request contains all required input fields for {spec.name}.",
            params={"payload": dict(payload)},
        )


def build_task_decision(
    spec: TaskSpec,
    payload: dict[str, Any],
    planner: DecisionPlanner | None = None,
) -> TaskDecision:
    resolved_planner = planner or DecisionPlanner()
    return resolved_planner.decide(spec, payload)
