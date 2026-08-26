"""
Scoped Tool: restore_configuration for AEGIS Ω.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class RestoreConfigurationParams(BaseModel):
    """Parameter schema for restore_configuration tool."""
    asset_id: str = Field(min_length=1, description="Target asset identifier")
    config_snapshot_id: str = Field(min_length=1, description="Snapshot ID of configuration to restore")


async def restore_configuration(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute restore_configuration tool with strict Pydantic validation."""
    validated = RestoreConfigurationParams.model_validate(params)
    return await client.restore_configuration(
        asset_id=validated.asset_id,
        config_snapshot_id=validated.config_snapshot_id,
    )
