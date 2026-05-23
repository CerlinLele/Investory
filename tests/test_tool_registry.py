from pydantic import BaseModel

from investory.agent_core.tools import ToolRegistry, UnknownToolError


class RegistryToolInput(BaseModel):
    query: str


class RegistryToolOutput(BaseModel):
    answer: str


class RegistryTool:
    def __init__(self, name: str, answer: str) -> None:
        self.name = name
        self.description = f"Registry test tool for {name}."
        self.input_model = RegistryToolInput
        self.output_model = RegistryToolOutput
        self._answer = answer

    def run(self, payload: BaseModel) -> BaseModel:
        self.input_model.model_validate(payload)
        return self.output_model(answer=self._answer)


def test_tool_registry_registers_and_gets_tool():
    tool = RegistryTool("lookup_test", "first")
    registry = ToolRegistry()

    registry.register(tool)

    assert registry.get("lookup_test") is tool


def test_tool_registry_accepts_initial_tools():
    first = RegistryTool("beta_tool", "beta")
    second = RegistryTool("alpha_tool", "alpha")

    registry = ToolRegistry([first, second])

    assert registry.get("alpha_tool") is second
    assert registry.get("beta_tool") is first


def test_tool_registry_lists_names_in_sorted_order():
    registry = ToolRegistry(
        [
            RegistryTool("zeta_tool", "zeta"),
            RegistryTool("alpha_tool", "alpha"),
        ]
    )

    assert registry.list_names() == ["alpha_tool", "zeta_tool"]


def test_tool_registry_raises_for_unknown_tool():
    registry = ToolRegistry()

    try:
        registry.get("missing_tool")
    except UnknownToolError as exc:
        assert str(exc) == "Unknown tool: missing_tool"
    else:
        raise AssertionError("Expected UnknownToolError")


def test_tool_registry_allows_duplicate_registration_to_override():
    original = RegistryTool("lookup_test", "original")
    replacement = RegistryTool("lookup_test", "replacement")
    registry = ToolRegistry([original])

    registry.register(replacement)

    assert registry.get("lookup_test") is replacement
