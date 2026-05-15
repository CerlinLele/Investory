from datetime import date

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.tools.net_guard import GuardedHttpResult, guarded_get

ALLOWED_HOSTS: tuple[str, ...] = (
    "example.com",
    "www.example.com",
)
DEFAULT_TIMEOUT_SECONDS = 8
MAX_SOURCE_MATERIAL_CHARS = 3000


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

        source_material = (result.text or "").strip()[:MAX_SOURCE_MATERIAL_CHARS]
        if not source_material:
            last_error = GuardedHttpResult(
                ok=False,
                error_type="parse_error",
                error_message=f"Empty source content from '{source}'.",
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
