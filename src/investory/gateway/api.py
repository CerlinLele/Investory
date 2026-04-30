"""HTTP routes for the Investory gateway."""

from __future__ import annotations

from fastapi import APIRouter, Request

from investory.gateway.schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    config = request.app.state.config

    return HealthResponse(
        ok=True,
        app_name=config.app_name,
        app_env=config.app_env,
    )
