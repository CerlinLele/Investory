from datetime import date
import re
from typing import Literal

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.config import load_config
from investory.agent_core.tools.http_runner import (
    Candidate,
    ParseOutcome,
    run_guarded_candidates,
)
from investory.agent_core.tools.net_guard import GuardedHttpResult, guarded_get

ErrorType = Literal[
    "invalid_input",
    "blocked_host",
    "timeout",
    "network_error",
    "parse_error",
    "not_found",
]
TOOL_NAME = "fetch_instrument_profile"

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


def _build_candidate_sources(normalized: str) -> list[Candidate]:
    return [
        Candidate(
            id=f"https://example.com/instruments/{normalized}",
            url=f"https://example.com/instruments/{normalized}",
        ),
        Candidate(
            id=f"https://www.example.com/search?q={normalized}",
            url=f"https://www.example.com/search?q={normalized}",
        ),
        Candidate(
            id="https://example.com/factsheet",
            url="https://example.com/factsheet",
        ),
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
        tool_name=TOOL_NAME,
        ok=False,
        error_type=error_type,
        error_message=last_error.error_message or "Failed to fetch instrument profile.",
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def _build_error_result(error_type: ErrorType, error_message: str) -> ToolResult:
    return ToolResult(
        tool_name=TOOL_NAME,
        ok=False,
        error_type=error_type,
        error_message=error_message,
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def fetch_instrument_profile(instrument_name_or_code: str) -> ToolResult:
    normalized = instrument_name_or_code.strip().upper()
    if not normalized:
        return _build_error_result(
            error_type="invalid_input",
            error_message="instrument_name_or_code is required.",
        )

    def _parse_success(candidate: Candidate, text: str) -> ParseOutcome:
        extracted = _extract_profile_text(text)
        source_material = _build_source_material(normalized, extracted)
        if len(extracted) < MIN_SOURCE_MATERIAL_CHARS:
            return ParseOutcome(
                ok=False,
                error_type="parse_error",
                error_message=f"Insufficient source content from '{candidate.url}'.",
            )
        return ParseOutcome(ok=True, item=source_material)

    outcome = run_guarded_candidates(
        tool_name=TOOL_NAME,
        candidates=_build_candidate_sources(normalized),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        allowed_hosts=ALLOWED_HOSTS,
        user_agent=TOOL_USER_AGENT,
        parse_success=_parse_success,
        max_successes=1,
        guarded_get_fn=guarded_get,
    )

    if not outcome.items:
        return _build_failure_result(normalized, outcome.last_error)

    return ToolResult(
        tool_name=TOOL_NAME,
        ok=True,
        data={
            "instrument_name_or_code": normalized,
            "source_material": outcome.items[0],
            "sources": outcome.attempt_order,
            "as_of": date.today().isoformat(),
        },
    )
