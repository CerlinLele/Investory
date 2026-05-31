from pydantic import BaseModel

from investory.agent_core.runtime.react_core.tool_registry import (
    CONFIRMATION_GRANTED_ARG,
    ToolRegistry,
    ToolSpec,
    ToolValidationErrorCode,
)


class SearchArgs(BaseModel):
    query: str
    limit: int = 5


def test_tool_registry_register_and_get() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(name="search_docs", args_model=SearchArgs)

    registry.register(spec)

    loaded = registry.get("search_docs")
    assert loaded is not None
    assert loaded.name == "search_docs"


def test_validate_returns_error_when_tool_not_registered() -> None:
    registry = ToolRegistry()

    result = registry.validate("missing_tool", {"query": "react"}, task_name="qa")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ToolValidationErrorCode.TOOL_NOT_REGISTERED


def test_validate_returns_error_when_task_not_allowed() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_docs",
            args_model=SearchArgs,
            allowed_task_names=frozenset({"summary"}),
        )
    )

    result = registry.validate("search_docs", {"query": "react"}, task_name="qa")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ToolValidationErrorCode.TOOL_NOT_ALLOWED_FOR_TASK


def test_validate_returns_error_when_confirmation_is_required() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_docs",
            args_model=SearchArgs,
            requires_confirmation=True,
        )
    )

    result = registry.validate("search_docs", {"query": "react"}, task_name="qa")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ToolValidationErrorCode.CONFIRMATION_REQUIRED


def test_validate_returns_error_when_args_invalid() -> None:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="search_docs", args_model=SearchArgs))

    result = registry.validate("search_docs", {"limit": "bad"}, task_name="qa")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == ToolValidationErrorCode.INVALID_TOOL_ARGS
    assert "errors" in result.error.details


def test_validate_returns_normalized_args_on_success() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="search_docs",
            args_model=SearchArgs,
            requires_confirmation=True,
            allowed_task_names=frozenset({"qa"}),
        )
    )

    result = registry.validate(
        "search_docs",
        {
            "query": "react loop",
            "limit": 3,
            CONFIRMATION_GRANTED_ARG: True,
        },
        task_name="qa",
    )

    assert result.ok is True
    assert result.error is None
    assert result.normalized_args == {"query": "react loop", "limit": 3}
    assert result.requires_confirmation is True
