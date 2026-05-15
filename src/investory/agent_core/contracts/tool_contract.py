from typing import Any, Literal

from pydantic import BaseModel, Field


ToolName = Literal["fetch_instrument_profile", "web_search"]


class ToolCall(BaseModel):
    tool_name: ToolName
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Tool input params. For web_search, recommended keys are: "
            "query (str), top_k (int, optional), provider_hint (str, optional)."
        ),
    )
    request_id: str | None = None


class ToolResult(BaseModel):
    tool_name: str
    ok: bool
    data: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    retryable: bool = False
