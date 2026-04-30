from uuid import UUID

from investory.gateway.session import resolve_session_id


def test_resolve_session_id_reuses_existing_session_id():
    assert resolve_session_id("session-1") == "session-1"


def test_resolve_session_id_strips_existing_session_id():
    assert resolve_session_id("  session-1  ") == "session-1"


def test_resolve_session_id_generates_uuid_when_missing():
    session_id = resolve_session_id()

    parsed = UUID(session_id)
    assert parsed.version == 4


def test_resolve_session_id_generates_unique_ids():
    first = resolve_session_id()
    second = resolve_session_id()

    assert first != second


def test_resolve_session_id_generates_uuid_for_blank_input():
    session_id = resolve_session_id("  ")

    parsed = UUID(session_id)
    assert parsed.version == 4
