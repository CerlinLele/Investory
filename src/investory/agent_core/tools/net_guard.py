import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "InvestoryBot/0.1 (+https://investory.local)"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuardValidation:
    ok: bool
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class GuardedHttpResult:
    ok: bool
    status_code: int | None = None
    text: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    retryable: bool = False


def log_http_attempt(
    *,
    tool_name: str,
    host: str,
    elapsed_ms: int,
    success: bool,
    error_type: str | None = None,
) -> None:
    LOGGER.info(
        "tool_http_attempt",
        extra={
            "tool_name": tool_name,
            "target_host": host,
            "elapsed_ms": elapsed_ms,
            "success": success,
            "error_type": error_type,
        },
    )


def validate_url(url: str, allowed_hosts: tuple[str, ...]) -> GuardValidation:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return GuardValidation(
            ok=False,
            error_type="blocked_host",
            error_message="Only https sources are allowed.",
        )

    host = (parsed.hostname or "").lower()
    if not host or host not in allowed_hosts:
        return GuardValidation(
            ok=False,
            error_type="blocked_host",
            error_message=f"Host '{host or 'unknown'}' is not allowed.",
        )

    return GuardValidation(ok=True)


def guarded_get(
    url: str,
    *,
    timeout: int,
    allowed_hosts: tuple[str, ...],
    user_agent: str = DEFAULT_USER_AGENT,
) -> GuardedHttpResult:
    validation = validate_url(url, allowed_hosts=allowed_hosts)
    if not validation.ok:
        return GuardedHttpResult(
            ok=False,
            error_type=validation.error_type,
            error_message=validation.error_message,
            retryable=False,
        )

    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            encoding = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(encoding, errors="replace")
            if "text" not in content_type and "json" not in content_type:
                return GuardedHttpResult(
                    ok=False,
                    error_type="parse_error",
                    error_message=f"Unsupported content type: {content_type or 'unknown'}",
                    retryable=False,
                )
            return GuardedHttpResult(
                ok=True,
                status_code=getattr(response, "status", 200),
                text=body,
            )
    except TimeoutError:
        return GuardedHttpResult(
            ok=False,
            error_type="timeout",
            error_message="HTTP request timed out.",
            retryable=True,
        )
    except HTTPError as exc:
        if exc.code == 404:
            return GuardedHttpResult(
                ok=False,
                error_type="not_found",
                error_message="Resource not found.",
                retryable=False,
            )
        retryable = 500 <= exc.code < 600
        return GuardedHttpResult(
            ok=False,
            error_type="network_error",
            error_message=f"HTTP request failed with status {exc.code}.",
            retryable=retryable,
        )
    except URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        return GuardedHttpResult(
            ok=False,
            error_type="network_error",
            error_message=f"Network error: {reason}",
            retryable=True,
        )
