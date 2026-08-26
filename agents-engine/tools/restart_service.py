"""
Scoped Tool: restart_service for AEGIS Ω.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class RestartServiceParams(BaseModel):
    """Parameter schema for restart_service tool."""
    asset_id: str = Field(min_length=1, description="Target asset identifier to restart")
    grace_period_sec: int = Field(default=15, ge=0, le=300, description="Grace period duration in seconds")


async def restart_service(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute restart_service tool with strict Pydantic validation."""
    validated = RestartServiceParams.model_validate(params)
    return await client.restart_service(
        asset_id=validated.asset_id,
        grace_period_sec=validated.grace_period_sec,
    )
