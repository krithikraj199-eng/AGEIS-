"""
Scoped Tool: rollback_deployment for AEGIS Ω.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class RollbackDeploymentParams(BaseModel):
    """Parameter schema for rollback_deployment tool."""
    asset_id: str = Field(min_length=1, description="Target asset identifier to rollback")
    target_version: str = Field(min_length=1, description="Target version tag or release hash to revert to")


async def rollback_deployment(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute rollback_deployment tool with strict Pydantic validation."""
    validated = RollbackDeploymentParams.model_validate(params)
    return await client.rollback_deployment(
        asset_id=validated.asset_id,
        target_version=validated.target_version,
    )
