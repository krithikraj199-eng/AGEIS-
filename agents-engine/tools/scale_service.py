"""
Scoped Tool: scale_service for AEGIS Ω.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class ScaleServiceParams(BaseModel):
    """Parameter schema for scale_service tool."""
    asset_id: str = Field(min_length=1, description="Target asset identifier to scale")
    factor: float = Field(default=2.0, gt=0.0, le=10.0, description="Scaling factor multiplier")
    replicas: Optional[int] = Field(default=None, ge=1, le=50, description="Explicit target replica count")


async def scale_service(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute scale_service tool with strict Pydantic validation."""
    validated = ScaleServiceParams.model_validate(params)
    return await client.scale_service(
        asset_id=validated.asset_id,
        factor=validated.factor,
        replicas=validated.replicas,
    )
