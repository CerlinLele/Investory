from datetime import date
from urllib.parse import urlparse

from investory.agent_core.contracts.tool_contract import ToolResult

ALLOWED_HOSTS: tuple[str, ...] = (
    "example.com",
    "www.example.com",
)
DEFAULT_TIMEOUT_SECONDS = 8
MAX_SOURCE_MATERIAL_CHARS = 3000


def _is_allowed_source_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_HOSTS


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

    # Step 1: freeze source strategy with allowlisted https URLs and structured text only.
    sources = [
        f"https://example.com/instruments/{normalized}",
        "https://example.com/factsheet",
    ]
    filtered_sources = [url for url in sources if _is_allowed_source_url(url)]
    source_material = (
        f"{normalized} mock profile: this is a placeholder public summary "
        "used for learning-brief generation."
    )[:MAX_SOURCE_MATERIAL_CHARS]

    return ToolResult(
        tool_name="fetch_instrument_profile",
        ok=True,
        data={
            "instrument_name_or_code": normalized,
            "source_material": source_material,
            "sources": filtered_sources,
            "as_of": date.today().isoformat(),
        },
    )
