"""
Scoped Tool: quarantine_asset for AEGIS Ω.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class QuarantineAssetParams(BaseModel):
    """Parameter schema for quarantine_asset tool."""
    asset_id: str = Field(min_length=1, description="Target asset identifier to isolate")
    reason: str = Field(default="security_isolation", description="Reason for quarantine")


async def quarantine_asset(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute quarantine_asset tool with strict Pydantic validation."""
    validated = QuarantineAssetParams.model_validate(params)
    return await client.quarantine_asset(
        asset_id=validated.asset_id,
        reason=validated.reason,
    )
