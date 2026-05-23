from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class ToolSource(BaseModel):
    provider: str
    source_url: str | None = None
    as_of: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    elapsed_ms: int | None = None


class ToolExecutionError(Exception):
    pass


@runtime_checkable
class ToolExecutor(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def run(self, payload: BaseModel) -> BaseModel:
        ...
