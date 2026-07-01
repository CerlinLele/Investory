import pytest
from pydantic import BaseModel

from investory.agent_core.runtime.react_core.tool_registry import ToolRegistry, ToolSpec


class SimpleArgs(BaseModel):
    value: str


def dummy_func(value: str) -> dict[str, str]:
    return {"result": value}


def test_list_all_returns_all_tools() -> None:
    registry = ToolRegistry()
    spec1 = ToolSpec(
        name="tool1",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Tool 1",
        side_effect_level="read",
        tag="test",
    )
    spec2 = ToolSpec(
        name="tool2",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Tool 2",
        side_effect_level="write",
        tag="test",
    )
    registry.register(spec1)
    registry.register(spec2)

    specs = registry.list_all()

    assert len(specs) == 2
    assert {spec["name"] for spec in specs} == {"tool1", "tool2"}


def test_list_by_tag() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="query_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            tag="query",
        )
    )
    registry.register(
        ToolSpec(
            name="write_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            tag="write",
        )
    )

    query_specs = registry.list_by_tag("query")

    assert len(query_specs) == 1
    assert query_specs[0]["name"] == "query_tool"


def test_list_by_side_effect() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            side_effect_level="read",
        )
    )
    registry.register(
        ToolSpec(
            name="write_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            side_effect_level="write",
        )
    )

    write_specs = registry.list_by_side_effect("write")

    assert len(write_specs) == 1
    assert write_specs[0]["name"] == "write_tool"


def test_get_func() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            desc="Test Tool",
        )
    )

    func = registry.get_func("test_tool")

    assert func is not None
    assert func("hello") == {"result": "hello"}


def test_call_func() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="test_tool",
            args_model=SimpleArgs,
            func=dummy_func,
            desc="Test Tool",
        )
    )

    result = registry.call_func("test_tool", {"value": "world"})

    assert result == {"result": "world"}


def test_call_func_not_found() -> None:
    registry = ToolRegistry()

    with pytest.raises(ValueError):
        registry.call_func("nonexistent", {})
