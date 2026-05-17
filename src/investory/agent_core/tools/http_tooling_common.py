import re
from typing import Literal

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.tools.net_guard import GuardedHttpResult

ErrorType = Literal[
    "invalid_input",
    "blocked_host",
    "timeout",
    "network_error",
    "parse_error",
    "not_found",
]

DEFAULT_ERROR_RETRYABLE_POLICY: dict[ErrorType, bool] = {
    "invalid_input": False,
    "blocked_host": False,
    "timeout": True,
    "network_error": True,
    "parse_error": False,
    "not_found": False,
}


def normalize_html_text(raw_text: str) -> str:
    text = raw_text or ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def build_error_result(
    *,
    tool_name: str,
    error_type: ErrorType,
    error_message: str,
    error_retryable_policy: dict[ErrorType, bool],
) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        ok=False,
        error_type=error_type,
        error_message=error_message,
        retryable=error_retryable_policy[error_type],
    )


def build_failure_result(
    *,
    tool_name: str,
    last_error: GuardedHttpResult | None,
    not_found_message: str,
    default_error_message: str,
    error_retryable_policy: dict[ErrorType, bool],
) -> ToolResult:
    if last_error is None:
        return build_error_result(
            tool_name=tool_name,
            error_type="not_found",
            error_message=not_found_message,
            error_retryable_policy=error_retryable_policy,
        )

    raw_error_type = (last_error.error_type or "network_error").lower()
    error_type: ErrorType = (
        raw_error_type if raw_error_type in error_retryable_policy else "network_error"
    )
    return ToolResult(
        tool_name=tool_name,
        ok=False,
        error_type=error_type,
        error_message=last_error.error_message or default_error_message,
        retryable=error_retryable_policy[error_type],
    )
