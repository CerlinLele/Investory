from datetime import date

from investory.agent_core.contracts.tool_contract import ToolResult


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

    # Mock data for step 2. This will be replaced by real public-source fetching later.
    return ToolResult(
        tool_name="fetch_instrument_profile",
        ok=True,
        data={
            "instrument_name_or_code": normalized,
            "source_material": (
                f"{normalized} mock profile: this is a placeholder public summary "
                "used for learning-brief generation."
            ),
            "sources": [
                f"https://example.com/instruments/{normalized}",
                "https://example.com/factsheet",
            ],
            "as_of": date.today().isoformat(),
        },
    )
