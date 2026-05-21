from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from investory.agent_core.contracts.task_spec import TaskSpec


def get_required_fields(spec: "TaskSpec") -> list[str]:
    return [
        field_name
        for field_name, field_info in spec.input_model.model_fields.items()
        if field_info.is_required()
    ]


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str) and value.strip() == "":
        return True

    return False


def get_missing_required_fields(spec: "TaskSpec", payload: dict[str, Any]) -> list[str]:
    return [
        field_name
        for field_name in get_required_fields(spec)
        if field_name not in payload or _is_missing_value(payload[field_name])
    ]
