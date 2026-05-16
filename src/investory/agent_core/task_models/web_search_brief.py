from pydantic import BaseModel, Field


class WebSearchBriefInput(BaseModel):
    query: str = Field(description="Search query for web lookup.")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum result count.")
    provider_hint: str | None = Field(
        default=None,
        description="Optional preferred provider name.",
    )


class WebSearchResultItem(BaseModel):
    title: str = Field(description="Result title.")
    url: str = Field(description="Result URL.")
    snippet: str = Field(description="Result snippet.")
    source: str = Field(description="Result source host.")
    provider: str = Field(description="Provider adapter name.")


class WebSearchBriefResult(BaseModel):
    query: str = Field(description="Normalized query.")
    results: list[WebSearchResultItem] = Field(description="Structured search results.")
    provider_attempt_order: list[str] = Field(
        description="Provider attempt order for fallback traceability."
    )
