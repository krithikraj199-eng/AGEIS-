"""
Tool Registry and Dispatcher for AEGIS Ω.
Enforces Pydantic schema validation, tool whitelisting, and execution routing to DigitalWorldClient.
"""

from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import ValidationError

from .client import DigitalWorldClientProtocol, MockDigitalWorldClient
from .restart_service import restart_service, RestartServiceParams
from .scale_service import scale_service, ScaleServiceParams
from .rollback_deployment import rollback_deployment, RollbackDeploymentParams
from .clear_cache import clear_cache, ClearCacheParams
from .quarantine_asset import quarantine_asset, QuarantineAssetParams
from .restore_configuration import restore_configuration, RestoreConfigurationParams


class ToolExecutionResult:
    """Standardized tool execution result."""
    def __init__(
        self,
        success: bool,
        tool_name: str,
        result: Dict[str, Any],
        error_message: Optional[str] = None,
    ):
        self.success = success
        self.tool_name = tool_name
        self.result = result
        self.error_message = error_message


class ToolRegistry:
    """
    Central registry for all approved remediation tools.
    Validates tool names and argument schemas before dispatching.
    """

    TOOLS: Dict[str, Callable[[DigitalWorldClientProtocol, Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]] = {
        "restart_service": restart_service,
        "scale_service": scale_service,
        "rollback_deployment": rollback_deployment,
        "clear_cache": clear_cache,
        "quarantine_asset": quarantine_asset,
        "restore_configuration": restore_configuration,
    }

    def __init__(self, client: Optional[DigitalWorldClientProtocol] = None):
        self.client = client or MockDigitalWorldClient()

    def is_tool_allowed(self, tool_name: str) -> bool:
        return tool_name in self.TOOLS

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> ToolExecutionResult:
        """
        Execute a tool by name with strict validation.
        """
        if not self.is_tool_allowed(tool_name):
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result={},
                error_message=f"Disallowed or unknown tool '{tool_name}'. Allowed: {list(self.TOOLS.keys())}",
            )

        tool_func = self.TOOLS[tool_name]
        try:
            res = await tool_func(self.client, params)
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                result=res,
            )
        except ValidationError as ve:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result={},
                error_message=f"Parameter validation failed for tool '{tool_name}': {ve}",
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result={},
                error_message=f"Execution error in tool '{tool_name}': {e}",
            )
