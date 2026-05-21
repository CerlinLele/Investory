"""Minimal session helpers for the HTTP gateway."""

from __future__ import annotations

from uuid import uuid4


def resolve_session_id(session_id: str | None = None) -> str:
    """Return the provided session ID or generate a new one."""

    if session_id is not None:
        normalized = session_id.strip()
        if normalized:
            return normalized

    return str(uuid4())


__all__ = ["resolve_session_id"]
