from investory.agent_core.tools.contracts import ToolExecutor


class UnknownToolError(ValueError):
    pass


class ToolRegistry:
    def __init__(self, tools: list[ToolExecutor] | None = None) -> None:
        self._tools: dict[str, ToolExecutor] = {
            tool.name: tool for tool in tools or []
        }

    def register(self, tool: ToolExecutor) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolExecutor:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(f"Unknown tool: {name}") from exc

    def list_names(self) -> list[str]:
        return sorted(self._tools)
