from typing import Any

from investory.agent_core.contracts.learning_entry_state import (
    LearningEntryCandidateTaskType,
)


MATERIAL_TEXT_FIELD = "material_text"
QUESTION_FIELD = "question"
INSTRUMENT_NAME_OR_CODE_FIELD = "instrument_name_or_code"
SOURCE_MATERIAL_FIELD = "source_material"
REQUIRES_REALTIME_DATA_FIELD = "requires_realtime_data"
REQUIRES_CONFIRMATION_FIELD = "requires_confirmation"
CONFIRMATION_GRANTED_FIELD = "confirmation_granted"

UNKNOWN_INPUT_MISSING_FIELDS = [
    MATERIAL_TEXT_FIELD,
    QUESTION_FIELD,
    INSTRUMENT_NAME_OR_CODE_FIELD,
    SOURCE_MATERIAL_FIELD,
]

INVESTMENT_ADVICE_TERMS = (
    "buy",
    "sell",
    "should i invest",
    "should i buy",
    "should i sell",
    "recommend",
    "allocation",
    "position size",
    "买",
    "卖",
    "买入",
    "卖出",
    "该不该",
    "适合买吗",
    "能买吗",
    "要不要买",
    "配置",
    "仓位",
    "择时",
)

REALTIME_DATA_TERMS = (
    "real-time",
    "realtime",
    "latest price",
    "current price",
    "today price",
    "live quote",
    "实时",
    "最新价格",
    "当前价格",
    "行情",
)

CONFIRMATION_TERMS = (
    "execute now",
    "run now",
    "perform action",
    "place order",
    "submit order",
    "确认执行",
    "立即执行",
    "下单",
)


def _has_value(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def payload_to_text(payload: dict[str, Any]) -> str:
    return " ".join(str(value) for value in payload.values()).lower()


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


def looks_like_investment_advice(payload: dict[str, Any]) -> bool:
    text = payload_to_text(payload)
    return any(term in text for term in INVESTMENT_ADVICE_TERMS)


def requires_realtime_data(payload: dict[str, Any]) -> bool:
    if _as_bool(payload.get(REQUIRES_REALTIME_DATA_FIELD)):
        return True
    text = payload_to_text(payload)
    return any(term in text for term in REALTIME_DATA_TERMS)


def requires_user_confirmation(payload: dict[str, Any]) -> bool:
    if _as_bool(payload.get(REQUIRES_CONFIRMATION_FIELD)):
        return True
    text = payload_to_text(payload)
    return any(term in text for term in CONFIRMATION_TERMS)


def has_user_confirmation(payload: dict[str, Any]) -> bool:
    return _as_bool(payload.get(CONFIRMATION_GRANTED_FIELD))
