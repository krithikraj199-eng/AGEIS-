"""
Scoped Tool: clear_cache for AEGIS Ω.
"""

from typing import Any, Dict
from pydantic import BaseModel, Field
from .client import DigitalWorldClientProtocol


class ClearCacheParams(BaseModel):
    """Parameter schema for clear_cache tool."""
    asset_id: str = Field(min_length=1, description="Target cache asset identifier")
    cache_pattern: str = Field(default="*", description="Cache key pattern to invalidate")


async def clear_cache(
    client: DigitalWorldClientProtocol,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute clear_cache tool with strict Pydantic validation."""
    validated = ClearCacheParams.model_validate(params)
    return await client.clear_cache(
        asset_id=validated.asset_id,
        cache_pattern=validated.cache_pattern,
    )
