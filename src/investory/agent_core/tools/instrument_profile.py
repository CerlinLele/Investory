from datetime import date
import logging
import re
import time
from typing import Literal
from urllib.parse import urlparse

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.config import load_config
from investory.agent_core.tools.net_guard import GuardedHttpResult, guarded_get

ErrorType = Literal[
    "invalid_input",
    "blocked_host",
    "timeout",
    "network_error",
    "parse_error",
    "not_found",
]

_APP_CONFIG = load_config()
ALLOWED_HOSTS: tuple[str, ...] = _APP_CONFIG.tool_allowed_hosts
DEFAULT_TIMEOUT_SECONDS = _APP_CONFIG.tool_http_timeout_seconds
TOOL_USER_AGENT = _APP_CONFIG.tool_user_agent
MAX_SOURCE_MATERIAL_CHARS = 3000
MIN_SOURCE_MATERIAL_CHARS = 40
ERROR_RETRYABLE_POLICY: dict[ErrorType, bool] = {
    "invalid_input": False,
    "blocked_host": False,
    "timeout": True,
    "network_error": True,
    "parse_error": False,
    "not_found": False,
}
LOGGER = logging.getLogger(__name__)


def _extract_profile_text(raw_text: str) -> str:
    text = raw_text or ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_SOURCE_MATERIAL_CHARS]


def _build_source_material(instrument_name_or_code: str, profile_text: str) -> str:
    summary = (
        f"Instrument: {instrument_name_or_code}\n"
        f"Profile Summary: {profile_text.strip()}"
    ).strip()
    return summary[:MAX_SOURCE_MATERIAL_CHARS]


def _build_candidate_sources(normalized: str) -> list[str]:
    return [
        f"https://example.com/instruments/{normalized}",
        f"https://www.example.com/search?q={normalized}",
        "https://example.com/factsheet",
    ]


def _build_failure_result(
    normalized: str, last_error: GuardedHttpResult | None
) -> ToolResult:
    if last_error is None:
        return _build_error_result(
            error_type="not_found",
            error_message=f"No reachable source found for '{normalized}'.",
        )

    error_type = (last_error.error_type or "network_error").lower()
    if error_type not in ERROR_RETRYABLE_POLICY:
        error_type = "network_error"

    return ToolResult(
        tool_name="fetch_instrument_profile",
        ok=False,
        error_type=error_type,
        error_message=last_error.error_message or "Failed to fetch instrument profile.",
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def _build_error_result(error_type: ErrorType, error_message: str) -> ToolResult:
    return ToolResult(
        tool_name="fetch_instrument_profile",
        ok=False,
        error_type=error_type,
        error_message=error_message,
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def _log_tool_attempt(
    *,
    host: str,
    elapsed_ms: int,
    success: bool,
    error_type: str | None = None,
) -> None:
    LOGGER.info(
        "tool_http_attempt",
        extra={
            "tool_name": "fetch_instrument_profile",
            "target_host": host,
            "elapsed_ms": elapsed_ms,
            "success": success,
            "error_type": error_type,
        },
    )


def fetch_instrument_profile(instrument_name_or_code: str) -> ToolResult:
    normalized = instrument_name_or_code.strip().upper()
    if not normalized:
        return _build_error_result(
            error_type="invalid_input",
            error_message="instrument_name_or_code is required.",
        )

    sources = _build_candidate_sources(normalized)
    attempted_sources: list[str] = []
    last_error: GuardedHttpResult | None = None

    for source in sources:
        started_at = time.perf_counter()
        result = guarded_get(
            source,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            allowed_hosts=ALLOWED_HOSTS,
            user_agent=TOOL_USER_AGENT,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        host = urlparse(source).hostname or "unknown"
        attempted_sources.append(source)
        if not result.ok:
            _log_tool_attempt(
                host=host,
                elapsed_ms=elapsed_ms,
                success=False,
                error_type=result.error_type,
            )
            last_error = result
            continue

        extracted = _extract_profile_text(result.text or "")
        source_material = _build_source_material(normalized, extracted)
        if len(extracted) < MIN_SOURCE_MATERIAL_CHARS:
            _log_tool_attempt(
                host=host,
                elapsed_ms=elapsed_ms,
                success=False,
                error_type="parse_error",
            )
            last_error = GuardedHttpResult(
                ok=False,
                error_type="parse_error",
                error_message=f"Insufficient source content from '{source}'.",
                retryable=False,
            )
            continue
        _log_tool_attempt(
            host=host,
            elapsed_ms=elapsed_ms,
            success=True,
            error_type=None,
        )

        return ToolResult(
            tool_name="fetch_instrument_profile",
            ok=True,
            data={
                "instrument_name_or_code": normalized,
                "source_material": source_material,
                "sources": attempted_sources,
                "as_of": date.today().isoformat(),
            },
        )

    return _build_failure_result(normalized, last_error)
