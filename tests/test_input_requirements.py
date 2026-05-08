from pydantic import BaseModel

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.input_requirements import (
    get_missing_required_fields,
    get_required_fields,
)
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK


class MixedInput(BaseModel):
    required_text: str
    optional_text: str | None = None


class EmptyResult(BaseModel):
    ok: bool


def _mixed_spec() -> TaskSpec:
    return TaskSpec(
        name="mixed",
        prompt_name="mixed",
        input_model=MixedInput,
        output_model=EmptyResult,
    )


def test_get_required_fields_reads_pydantic_required_fields():
    assert get_required_fields(_mixed_spec()) == ["required_text"]


def test_get_missing_required_fields_ignores_optional_fields():
    assert get_missing_required_fields(_mixed_spec(), {}) == ["required_text"]


def test_get_missing_required_fields_treats_blank_strings_as_missing():
    assert get_missing_required_fields(
        _mixed_spec(),
        {"required_text": "  "},
    ) == ["required_text"]


def test_get_missing_required_fields_returns_empty_list_when_required_fields_exist():
    assert get_missing_required_fields(
        _mixed_spec(),
        {"required_text": "value"},
    ) == []


def test_get_missing_required_fields_for_instrument_brief_empty_payload():
    assert get_missing_required_fields(INSTRUMENT_BRIEF_TASK, {}) == [
        "instrument_name_or_code",
        "source_material",
    ]


def test_get_missing_required_fields_for_instrument_brief_partial_payload():
    assert get_missing_required_fields(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
    ) == ["source_material"]
