"""
MCP validate_connection action.

Validates MCP server connection reachability.
"""

import anyio
import time
from typing import Any, Dict, Optional

from pydantic import HttpUrl, Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType
from mas.core.enums import ResourceCategory
from mas.core.field_hints import SecretHint


# Input/Output models for this action
class ValidateConnectionInput(BaseActionInput):
    """Input for MCP connection validation"""
    mcp_url: HttpUrl
    bearer_token: Optional[str] = Field(
        default=None,
        description="Bearer token for MCP server authentication"
    )
    transport_type: McpTransportType = Field(
        default=McpTransportType.STREAMABLE_HTTP,
        description="Transport protocol for MCP server communication"
    )
    additional_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HTTP headers to include in MCP server requests"
    )


class ValidateConnectionOutput(BaseActionOutput):
    """Output for MCP connection validation"""
    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    """
    Validates MCP server connection.
    
    This action can work with any MCP-compatible element or independently.
    Single Responsibility: Only validates connection reachability
    """
    
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate that the MCP server endpoint is reachable and responding"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "1.0.0"
    tags = {"mcp", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}
    
    def __init__(self, factory: McpProviderFactory = None):
        """
        Initialize action with optional factory injection.
        
        Args:
            factory: McpProviderFactory instance (creates default if not provided)
        """
        super().__init__()
        self._factory = factory or McpProviderFactory()

    def execute_sync(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """
        Override execute_sync to handle MCP library's cancel scope corruption.
        
        The MCP library's streamablehttp_client has a bug where it corrupts
        anyio's cancel scope stack during connection failures. This causes a
        RuntimeError to be raised during the AsyncBridge's portal cleanup -
        AFTER the async code has finished executing.
        
        Because this error occurs outside the async execution context, it cannot
        be caught inside the async execute() method. We must catch it here at
        the sync boundary.
        
        This is a workaround for a third-party library bug, not a flaw in our
        AsyncBridge implementation.
        """
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            # Cancel scope errors from MCP library indicate connection failure
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=0.0
            )

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidateConnectionOutput:
        """
        Execute connection validation.

        Args:
            input_data: Validated connection input
            context: Optional execution context

        Returns:
            Validation result with connection status and timing
        """
        start_time = time.time()
        
        try:
            # Create config from input data
            config = McpProviderConfig(
                mcp_url=input_data.mcp_url,
                bearer_token=input_data.bearer_token,
                transport_type=input_data.transport_type,
                additional_headers=input_data.additional_headers,
            )
            
            # Create provider using factory - validates connection by fetching tools during init
            with anyio.fail_after(10.0):
                await self._factory.create_async(config)
            
            response_time = (time.time() - start_time) * 1000
            
            return ValidateConnectionOutput(
                success=True,
                message="Connection successful",
                is_reachable=True,
                response_time_ms=response_time
            )
            
        except TimeoutError:
            return ValidateConnectionOutput(
                success=False,
                message="Connection timeout - server may be unreachable",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {str(e)}",
                is_reachable=False,
                response_time_ms=(time.time() - start_time) * 1000
            )
