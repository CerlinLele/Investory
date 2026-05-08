from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from investory.agent_core.runtime.input_requirements import get_missing_required_fields

if TYPE_CHECKING:
    from investory.agent_core.contracts.task_spec import TaskSpec


ActionName = Literal["ask_missing_fields"]


class AskMissingFieldsAction(BaseModel):
    action: ActionName = "ask_missing_fields"
    task_name: str = Field(description="Task that needs more input before execution.")
    missing_fields: list[str] = Field(description="Required input fields missing from the payload.")
    user_message: str = Field(description="Message that can be shown to the user.")
    reason: str = Field(description="Internal reason for asking follow-up questions.")


def _humanize_fields(fields: list[str]) -> str:
    return ", ".join(fields)


def _instrument_brief_message(missing_fields: list[str]) -> str:
    missing = set(missing_fields)

    if missing == {"instrument_name_or_code", "source_material"}:
        return (
            "Please provide the instrument name or ticker/code, and paste the source "
            "material you want me to use, such as a fund description, ETF factsheet, "
            "news, or research excerpt."
        )

    if missing == {"instrument_name_or_code"}:
        return "Please provide the instrument name or ticker/code you want to study."

    if missing == {"source_material"}:
        return (
            "Please paste the source material you want me to use, such as a fund "
            "description, ETF factsheet, news, or research excerpt."
        )

    return f"Please provide the missing required fields: {_humanize_fields(missing_fields)}."


def _default_message(missing_fields: list[str]) -> str:
    return f"Please provide the missing required fields: {_humanize_fields(missing_fields)}."


def build_ask_missing_fields_action(
    *,
    task_name: str,
    missing_fields: Iterable[str],
) -> AskMissingFieldsAction:
    fields = list(missing_fields)
    if not fields:
        raise ValueError("missing_fields must contain at least one field.")

    user_message = (
        _instrument_brief_message(fields)
        if task_name == "instrument_brief"
        else _default_message(fields)
    )

    return AskMissingFieldsAction(
        task_name=task_name,
        missing_fields=fields,
        user_message=user_message,
        reason=(
            f"The request is missing required input fields for {task_name}: "
            f"{_humanize_fields(fields)}."
        ),
    )


def decide_missing_fields_action(
    spec: "TaskSpec",
    payload: dict,
) -> AskMissingFieldsAction | None:
    missing_fields = get_missing_required_fields(spec, payload)
    if not missing_fields:
        return None

    return build_ask_missing_fields_action(
        task_name=spec.name,
        missing_fields=missing_fields,
    )
