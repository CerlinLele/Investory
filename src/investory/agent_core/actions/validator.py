from typing import Any

from investory.agent_core.contracts.action_contract import ActionCall, TaskDecision
from investory.agent_core.contracts.task_spec import TaskSpec


class ActionValidationError(ValueError):
    """Raised when a task decision cannot be converted into an action call."""


def _ensure_action_allowed(decision: TaskDecision) -> None:
    allowed_actions = {
        "ask_missing_fields",
        "run_task_model",
        "refuse_investment_advice",
        "fetch_then_run_instrument_brief",
        "run_web_search",
    }
    if decision.action not in allowed_actions:
        raise ActionValidationError(f"Unsupported action: {decision.action}")


def _ensure_task_matches_spec(decision: TaskDecision, spec: TaskSpec) -> None:
    if decision.task_name != spec.name:
        raise ActionValidationError(
            f"Decision task_name {decision.task_name!r} does not match spec {spec.name!r}."
        )


def _ensure_dict_param(params: dict[str, Any], name: str) -> dict[str, Any]:
    value = params.get(name)
    if not isinstance(value, dict):
        raise ActionValidationError(f"{name} must be provided as a dict.")
    return value


def _ensure_non_empty_string_param(
    params: dict[str, Any],
    name: str,
) -> str | None:
    value = params.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ActionValidationError(f"{name} must be a non-empty string.")
    return value


def _validate_ask_missing_fields(decision: TaskDecision, spec: TaskSpec) -> None:
    missing_fields = decision.params.get("missing_fields")
    if not isinstance(missing_fields, list) or not missing_fields:
        raise ActionValidationError("missing_fields must be a non-empty list.")

    invalid_items = [field for field in missing_fields if not isinstance(field, str)]
    if invalid_items:
        raise ActionValidationError("missing_fields must contain only strings.")

    input_fields = set(spec.input_model.model_fields)
    unknown_fields = [field for field in missing_fields if field not in input_fields]
    if unknown_fields:
        unknown = ", ".join(unknown_fields)
        raise ActionValidationError(
            f"missing_fields contains fields not defined by {spec.name}: {unknown}."
        )


def _validate_run_task_model(decision: TaskDecision) -> None:
    _ensure_dict_param(decision.params, "payload")


def _validate_refuse_investment_advice(decision: TaskDecision) -> None:
    refused_reason = _ensure_non_empty_string_param(decision.params, "refused_reason")
    if decision.user_message is None and refused_reason is None:
        raise ActionValidationError(
            "refuse_investment_advice requires user_message or refused_reason."
        )

    _ensure_non_empty_string_param(decision.params, "allowed_alternative")


def _validate_fetch_then_run_instrument_brief(decision: TaskDecision) -> None:
    instrument_name_or_code = _ensure_non_empty_string_param(
        decision.params,
        "instrument_name_or_code",
    )
    if instrument_name_or_code is None:
        raise ActionValidationError(
            "fetch_then_run_instrument_brief requires instrument_name_or_code."
        )

    _ensure_dict_param(decision.params, "payload")


def _validate_run_web_search(decision: TaskDecision) -> None:
    query = _ensure_non_empty_string_param(decision.params, "query")
    if query is None:
        raise ActionValidationError("run_web_search requires query.")

    top_k = decision.params.get("top_k")
    if top_k is not None and (not isinstance(top_k, int) or top_k <= 0):
        raise ActionValidationError("top_k must be a positive integer when provided.")

    _ensure_non_empty_string_param(decision.params, "provider_hint")


def validate_decision(
    decision: TaskDecision,
    spec: TaskSpec,
    *,
    request_id: str | None = None,
) -> ActionCall:
    _ensure_action_allowed(decision)
    _ensure_task_matches_spec(decision, spec)

    if decision.action == "ask_missing_fields":
        _validate_ask_missing_fields(decision, spec)
    elif decision.action == "run_task_model":
        _validate_run_task_model(decision)
    elif decision.action == "refuse_investment_advice":
        _validate_refuse_investment_advice(decision)
    elif decision.action == "fetch_then_run_instrument_brief":
        _validate_fetch_then_run_instrument_brief(decision)
    elif decision.action == "run_web_search":
        _validate_run_web_search(decision)

    return ActionCall(
        action=decision.action,
        task_name=decision.task_name,
        params=dict(decision.params),
        decision_reason=decision.reason,
        request_id=request_id,
    )
