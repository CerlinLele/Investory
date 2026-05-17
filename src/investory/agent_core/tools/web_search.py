import re
from typing import Literal
from urllib.parse import quote_plus, urlparse

from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.tools.http_runner import (
    Candidate,
    ParseOutcome,
    run_guarded_candidates,
)
from investory.agent_core.tools.net_guard import GuardedHttpResult, guarded_get
from investory.config import load_config

ErrorType = Literal[
    "invalid_input",
    "blocked_host",
    "timeout",
    "network_error",
    "parse_error",
    "not_found",
]

TOOL_NAME = "web_search"
_APP_CONFIG = load_config()
ALLOWED_HOSTS: tuple[str, ...] = _APP_CONFIG.web_search_allowed_hosts
DEFAULT_TIMEOUT_SECONDS = _APP_CONFIG.web_search_timeout_seconds
TOOL_USER_AGENT = _APP_CONFIG.tool_user_agent
MAX_TOP_K = max(1, _APP_CONFIG.web_search_max_results)
DEFAULT_TOP_K = MAX_TOP_K
ERROR_RETRYABLE_POLICY: dict[ErrorType, bool] = {
    "invalid_input": False,
    "blocked_host": False,
    "timeout": True,
    "network_error": True,
    "parse_error": False,
    "not_found": False,
}

# Provider order is externally configurable for fallback governance.
PROVIDER_ORDER: tuple[str, ...] = _APP_CONFIG.web_search_provider_order


def _clamp_top_k(top_k: int) -> int:
    if top_k < 1:
        return 1
    if top_k > MAX_TOP_K:
        return MAX_TOP_K
    return top_k


def _build_error_result(error_type: ErrorType, error_message: str) -> ToolResult:
    return ToolResult(
        tool_name=TOOL_NAME,
        ok=False,
        error_type=error_type,
        error_message=error_message,
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def _parse_title(raw_text: str, *, fallback: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return fallback
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title or fallback


def _extract_snippet(raw_text: str, *, max_chars: int = 240) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw_text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _provider_candidates(query: str, provider_hint: str | None) -> list[Candidate]:
    normalized_query = quote_plus(query.strip())
    candidates = {
        "example_search": f"https://www.example.com/search?q={normalized_query}",
        "example_instruments": f"https://example.com/instruments/{normalized_query}",
    }

    ordered: list[str] = []
    if provider_hint and provider_hint in candidates:
        ordered.append(provider_hint)
    ordered.extend([name for name in PROVIDER_ORDER if name not in ordered])

    return [Candidate(id=provider, url=candidates[provider]) for provider in ordered if provider in candidates]


def _as_result_item(*, provider: str, url: str, html: str, query: str) -> dict[str, str]:
    parsed = urlparse(url)
    source = parsed.hostname or "unknown"
    return {
        "title": _parse_title(html, fallback=f"Search result for {query}"),
        "url": url,
        "snippet": _extract_snippet(html),
        "source": source,
        "provider": provider,
    }


def _build_failure_result(last_error: GuardedHttpResult | None) -> ToolResult:
    if last_error is None:
        return _build_error_result(
            error_type="not_found",
            error_message="No reachable search provider found.",
        )
    raw_error_type = (last_error.error_type or "network_error").lower()
    error_type: ErrorType = (
        raw_error_type if raw_error_type in ERROR_RETRYABLE_POLICY else "network_error"
    )
    return ToolResult(
        tool_name=TOOL_NAME,
        ok=False,
        error_type=error_type,
        error_message=last_error.error_message or "Web search failed.",
        retryable=ERROR_RETRYABLE_POLICY[error_type],
    )


def search_web(query: str, top_k: int = DEFAULT_TOP_K, provider_hint: str | None = None) -> ToolResult:
    normalized_query = query.strip()
    if not normalized_query:
        return _build_error_result(
            error_type="invalid_input",
            error_message="query is required.",
        )

    capped_top_k = _clamp_top_k(top_k)
    def _parse_success(candidate: Candidate, html: str) -> ParseOutcome:
        result_item = _as_result_item(
            provider=candidate.id,
            url=candidate.url,
            html=html,
            query=normalized_query,
        )
        if not result_item["snippet"]:
            return ParseOutcome(
                ok=False,
                error_type="parse_error",
                error_message=f"Provider '{candidate.id}' returned empty content.",
            )
        return ParseOutcome(ok=True, item=result_item)

    outcome = run_guarded_candidates(
        tool_name=TOOL_NAME,
        candidates=_provider_candidates(normalized_query, provider_hint),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        allowed_hosts=ALLOWED_HOSTS,
        user_agent=TOOL_USER_AGENT,
        parse_success=_parse_success,
        max_successes=capped_top_k,
        guarded_get_fn=guarded_get,
    )

    if not outcome.items:
        return _build_failure_result(outcome.last_error)

    return ToolResult(
        tool_name=TOOL_NAME,
        ok=True,
        data={
            "query": normalized_query,
            "results": outcome.items,
            "provider_attempt_order": outcome.attempt_order,
        },
    )
