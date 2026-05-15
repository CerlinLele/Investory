from datetime import date
import re

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.tools.net_guard import GuardedHttpResult, guarded_get

ALLOWED_HOSTS: tuple[str, ...] = (
    "example.com",
    "www.example.com",
)
DEFAULT_TIMEOUT_SECONDS = 8
MAX_SOURCE_MATERIAL_CHARS = 3000
MIN_SOURCE_MATERIAL_CHARS = 40


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
        return ToolResult(
            tool_name="fetch_instrument_profile",
            ok=False,
            error_type="not_found",
            error_message=f"No reachable source found for '{normalized}'.",
            retryable=False,
        )

    return ToolResult(
        tool_name="fetch_instrument_profile",
        ok=False,
        error_type=last_error.error_type or "network_error",
        error_message=last_error.error_message or "Failed to fetch instrument profile.",
        retryable=last_error.retryable,
    )


def fetch_instrument_profile(instrument_name_or_code: str) -> ToolResult:
    normalized = instrument_name_or_code.strip().upper()
    if not normalized:
        return ToolResult(
            tool_name="fetch_instrument_profile",
            ok=False,
            error_type="invalid_input",
            error_message="instrument_name_or_code is required.",
            retryable=False,
        )

    sources = _build_candidate_sources(normalized)
    attempted_sources: list[str] = []
    last_error: GuardedHttpResult | None = None

    for source in sources:
        result = guarded_get(
            source,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            allowed_hosts=ALLOWED_HOSTS,
        )
        attempted_sources.append(source)
        if not result.ok:
            last_error = result
            continue

        extracted = _extract_profile_text(result.text or "")
        source_material = _build_source_material(normalized, extracted)
        if len(extracted) < MIN_SOURCE_MATERIAL_CHARS:
            last_error = GuardedHttpResult(
                ok=False,
                error_type="parse_error",
                error_message=f"Insufficient source content from '{source}'.",
                retryable=False,
            )
            continue

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
