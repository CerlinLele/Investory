from typing import Any

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

DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE = {
    InvestmentDocumentType.ETF_FACTSHEET: DocumentReviewFramework(
        extract_focus=[
            "underlying index and tracking scope",
            "fees and expense ratios",
            "asset allocation composition",
            "historical performance disclosures",
        ],
        analyze_focus=[
            "risk disclosures completeness",
            "historical performance boundary statements",
            "cost impact on long-term returns",
        ],
    ),
    InvestmentDocumentType.FUND_PROSPECTUS: DocumentReviewFramework(
        extract_focus=[
            "investment scope and mandate",
            "fees and charges",
            "restrictions and limitations",
            "subscription and redemption rules",
        ],
        analyze_focus=[
            "key risk factors",
            "suitability constraints",
            "critical information gaps",
        ],
    ),
    InvestmentDocumentType.PRODUCT_BROCHURE: DocumentReviewFramework(
        extract_focus=[
            "product structure",
            "return claims and conditions",
            "applicability constraints",
        ],
        analyze_focus=[
            "potentially overstated return language",
            "risk disclosure sufficiency",
            "material caveat coverage",
        ],
    ),
    InvestmentDocumentType.EARNINGS_REPORT: DocumentReviewFramework(
        extract_focus=[
            "revenue and profit figures",
            "cash flow statements",
            "management commentary",
        ],
        analyze_focus=[
            "uncertainty disclosures",
            "non-extrapolatable conclusions",
            "fact versus inference boundaries",
        ],
    ),
    InvestmentDocumentType.LEARNING_MATERIAL: DocumentReviewFramework(
        extract_focus=[
            "core concepts and definitions",
            "mechanisms and examples",
            "key terminology",
        ],
        analyze_focus=[
            "learning priorities",
            "internal factual consistency",
            "material facts versus external assumptions",
        ],
    ),
}

def _intent_text(payload: dict[str, Any]) -> str:
    return join_text_fields(
        payload,
        (REVIEW_GOAL_FIELD, DOCUMENT_TYPE_HINT_FIELD),
    )


def detect_missing_fields(payload: dict[str, Any]) -> list[str]:
    if has_value(payload, DOCUMENT_TEXT_FIELD):
        return []
    return [DOCUMENT_TEXT_FIELD]


def looks_like_investment_advice(payload: dict[str, Any]) -> bool:
    text = _intent_text(payload)
    return any(term in text for term in INVESTMENT_ADVICE_TERMS)


def requires_realtime_data(payload: dict[str, Any]) -> bool:
    text = _intent_text(payload)
    return any(term in text for term in REALTIME_DATA_TERMS)


def build_document_excerpt(payload: dict[str, Any]) -> str:
    document_text = as_text(payload.get(DOCUMENT_TEXT_FIELD))
    return document_text[:DOCUMENT_ROUTER_MAX_CHARS]


def get_review_framework(
    document_type: InvestmentDocumentType,
) -> DocumentReviewFramework | None:
    if document_type == InvestmentDocumentType.UNKNOWN:
        return None
    return DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE.get(document_type)
