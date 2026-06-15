from collections.abc import Iterable
from typing import Any


def has_value(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "1", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def join_payload_values(payload: dict[str, Any]) -> str:
    return " ".join(as_text(value) for value in payload.values()).lower()


def join_text_fields(payload: dict[str, Any], field_names: Iterable[str]) -> str:
    return " ".join(as_text(payload.get(name)) for name in field_names).lower()

