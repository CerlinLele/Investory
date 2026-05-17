import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from investory.agent_core.tools.net_guard import (
    GuardedHttpResult,
    guarded_get,
    log_http_attempt,
)


@dataclass(frozen=True)
class Candidate:
    id: str
    url: str


@dataclass(frozen=True)
class ParseOutcome:
    ok: bool
    item: Any = None
    error_type: str = "parse_error"
    error_message: str | None = None


@dataclass(frozen=True)
class RunnerOutcome:
    items: list[Any]
    attempt_order: list[str]
    last_error: GuardedHttpResult | None


ParseSuccess = Callable[[Candidate, str], ParseOutcome]
GuardedGetFn = Callable[..., GuardedHttpResult]
LogAttemptFn = Callable[..., None]
NowFn = Callable[[], float]


def run_guarded_candidates(
    *,
    tool_name: str,
    candidates: list[Candidate],
    timeout_seconds: int,
    allowed_hosts: tuple[str, ...],
    user_agent: str,
    parse_success: ParseSuccess,
    max_successes: int = 1,
    guarded_get_fn: GuardedGetFn = guarded_get,
    log_attempt_fn: LogAttemptFn = log_http_attempt,
    now_fn: NowFn = time.perf_counter,
) -> RunnerOutcome:
    if max_successes < 1:
        max_successes = 1

    items: list[Any] = []
    attempt_order: list[str] = []
    last_error: GuardedHttpResult | None = None

    for candidate in candidates:
        started_at = now_fn()
        result = guarded_get_fn(
            candidate.url,
            timeout=timeout_seconds,
            allowed_hosts=allowed_hosts,
            user_agent=user_agent,
        )
        elapsed_ms = int((now_fn() - started_at) * 1000)
        host = urlparse(candidate.url).hostname or "unknown"
        attempt_order.append(candidate.id)

        if not result.ok:
            log_attempt_fn(
                tool_name=tool_name,
                host=host,
                elapsed_ms=elapsed_ms,
                success=False,
                error_type=result.error_type,
            )
            last_error = result
            continue

        parsed = parse_success(candidate, result.text or "")
        if not parsed.ok:
            parse_error_type = (parsed.error_type or "parse_error").lower()
            log_attempt_fn(
                tool_name=tool_name,
                host=host,
                elapsed_ms=elapsed_ms,
                success=False,
                error_type=parse_error_type,
            )
            last_error = GuardedHttpResult(
                ok=False,
                error_type=parse_error_type,
                error_message=parsed.error_message
                or f"Failed to parse response from candidate '{candidate.id}'.",
                retryable=False,
            )
            continue

        log_attempt_fn(
            tool_name=tool_name,
            host=host,
            elapsed_ms=elapsed_ms,
            success=True,
            error_type=None,
        )
        items.append(parsed.item)
        if len(items) >= max_successes:
            break

    return RunnerOutcome(
        items=items,
        attempt_order=attempt_order,
        last_error=last_error,
    )
