import re
from pathlib import Path
from typing import Any

import yaml

from investory.agent_core.contracts.investment_document_review_state import (
    DOCUMENT_TEXT_FIELD,
    DOCUMENT_TYPE_HINT_FIELD,
    REVIEW_GOAL_FIELD,
    DocumentReviewFramework,
    InvestmentDocumentType,
)
from investory.agent_core.runtime.flow.common.payload_rules import (
    as_text,
    has_value,
    join_text_fields,
)
from investory.config import PROJECT_ROOT


DOCUMENT_ROUTER_MAX_CHARS = 600
DEFAULT_DOCUMENT_ROUTE_CONFIDENCE_THRESHOLD = 0.6
UNKNOWN_DOCUMENT_MISSING_FIELDS = [DOCUMENT_TYPE_HINT_FIELD]

INVESTMENT_ADVICE_TERMS = (
    "buy",
    "sell",
    "hold",
    "should i invest",
    "should i buy",
    "should i sell",
    "allocation",
    "position size",
    "market timing",
    "buy or sell",
    "买入",
    "卖出",
    "持有",
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
    "today's price",
    "live quote",
    "price now",
    "today return",
    "latest move",
    "实时",
    "最新价格",
    "当前价格",
    "今天收益",
    "最新涨跌",
)

REVIEW_FRAMEWORK_CONFIG_PATH = PROJECT_ROOT / "config" / "review_frameworks.yaml"
KNOWN_REVIEW_FRAMEWORK_DOCUMENT_TYPES = (
    InvestmentDocumentType.ETF_FACTSHEET,
    InvestmentDocumentType.FUND_PROSPECTUS,
    InvestmentDocumentType.PRODUCT_BROCHURE,
    InvestmentDocumentType.EARNINGS_REPORT,
    InvestmentDocumentType.LEARNING_MATERIAL,
)


def _load_review_frameworks(
    config_path: Path = REVIEW_FRAMEWORK_CONFIG_PATH,
) -> dict[InvestmentDocumentType, DocumentReviewFramework]:
    config_payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config_payload, dict):
        raise ValueError("Review framework config must contain a top-level mapping.")

    frameworks: dict[InvestmentDocumentType, DocumentReviewFramework] = {}
    for document_type_value, framework_payload in config_payload.items():
        if not isinstance(document_type_value, str):
            raise ValueError(
                "Review framework config keys must be document type strings."
            )
        try:
            document_type = InvestmentDocumentType(document_type_value)
        except ValueError as exc:
            raise ValueError(
                f"Unknown document type in review framework config: {document_type_value}"
            ) from exc

        if document_type == InvestmentDocumentType.UNKNOWN:
            raise ValueError(
                "Review framework config must not define a framework for unknown."
            )

        if not isinstance(framework_payload, dict):
            raise ValueError(
                "Review framework config values must be object mappings."
            )

        frameworks[document_type] = DocumentReviewFramework.model_validate(
            framework_payload
        )

    missing_document_types = [
        document_type
        for document_type in KNOWN_REVIEW_FRAMEWORK_DOCUMENT_TYPES
        if document_type not in frameworks
    ]
    if missing_document_types:
        missing_values = ", ".join(
            document_type.value for document_type in missing_document_types
        )
        raise ValueError(
            "Review framework config is missing known document types: "
            f"{missing_values}"
        )

    return frameworks


DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE = _load_review_frameworks()

def _intent_text(payload: dict[str, Any]) -> str:
    return join_text_fields(
        payload,
        (REVIEW_GOAL_FIELD, DOCUMENT_TYPE_HINT_FIELD),
    )


def _contains_policy_term(text: str, term: str) -> bool:
    if term.isascii() and any(char.isalpha() for char in term):
        escaped_term = re.escape(term)
        pattern = rf"(?<![a-z0-9]){escaped_term}(?![a-z0-9])"
        return re.search(pattern, text) is not None
    return term in text


def _matches_any_policy_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_policy_term(text, term) for term in terms)


def detect_missing_fields(payload: dict[str, Any]) -> list[str]:
    if has_value(payload, DOCUMENT_TEXT_FIELD):
        return []
    return [DOCUMENT_TEXT_FIELD]


def looks_like_investment_advice(payload: dict[str, Any]) -> bool:
    text = _intent_text(payload)
    return _matches_any_policy_term(text, INVESTMENT_ADVICE_TERMS)


def requires_realtime_data(payload: dict[str, Any]) -> bool:
    text = _intent_text(payload)
    return _matches_any_policy_term(text, REALTIME_DATA_TERMS)


def build_document_excerpt(payload: dict[str, Any]) -> str:
    document_text = as_text(payload.get(DOCUMENT_TEXT_FIELD))
    return document_text[:DOCUMENT_ROUTER_MAX_CHARS]


def get_review_framework(
    document_type: InvestmentDocumentType,
) -> DocumentReviewFramework | None:
    if document_type == InvestmentDocumentType.UNKNOWN:
        return None
    return DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE.get(document_type)
