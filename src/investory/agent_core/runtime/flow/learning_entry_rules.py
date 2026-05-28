from typing import Any

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)


MATERIAL_TEXT_FIELD = "material_text"
QUESTION_FIELD = "question"
INSTRUMENT_NAME_OR_CODE_FIELD = "instrument_name_or_code"
SOURCE_MATERIAL_FIELD = "source_material"


def _has_value(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def detect_missing_fields(payload: dict[str, Any]) -> list[str]:
    missing_fields: list[str] = []

    has_material_text = _has_value(payload, MATERIAL_TEXT_FIELD)
    has_question = _has_value(payload, QUESTION_FIELD)
    has_instrument = _has_value(payload, INSTRUMENT_NAME_OR_CODE_FIELD)
    has_source_material = _has_value(payload, SOURCE_MATERIAL_FIELD)

    if has_question and not has_material_text:
        missing_fields.append(MATERIAL_TEXT_FIELD)

    if has_instrument and not has_source_material:
        missing_fields.append(SOURCE_MATERIAL_FIELD)

    if has_source_material and not has_instrument:
        missing_fields.append(INSTRUMENT_NAME_OR_CODE_FIELD)

    return missing_fields


def infer_candidate_task_type(
    payload: dict[str, Any],
) -> LearningEntryCandidateTaskType | None:
    has_material_text = _has_value(payload, MATERIAL_TEXT_FIELD)
    has_question = _has_value(payload, QUESTION_FIELD)
    has_instrument = _has_value(payload, INSTRUMENT_NAME_OR_CODE_FIELD)
    has_source_material = _has_value(payload, SOURCE_MATERIAL_FIELD)

    if has_material_text and has_question:
        return LearningEntryCandidateTaskType.QA

    if has_material_text:
        return LearningEntryCandidateTaskType.SUMMARY

    if has_instrument and has_source_material:
        return LearningEntryCandidateTaskType.BRIEF

    return None
