"""
elements/providers/mcp_server_client/validator.py

Validator for MCP Provider - checks endpoint reachability using McpProviderFactory.
"""

import anyio
from concurrent.futures import CancelledError
from typing import List

from global_utils.utils.async_bridge import get_async_bridge
from mas.elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory


class McpProviderValidator(BaseElementValidator):
    """
    Validates MCP Provider configuration.
    
    Checks:
    - MCP server connectivity
    - Ability to list tools from the server
    """

    def __init__(self, factory: McpProviderFactory = None):
        """
        Initialize validator with optional factory injection.
        
        Args:
            factory: McpProviderFactory instance (creates default if not provided)
        """
        super().__init__()
        self._factory = factory or McpProviderFactory()

    def validate(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate MCP provider config.
        
        Synchronous method - runs async checks internally using AsyncBridge.
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        try:
            with get_async_bridge() as bridge:
                bridge.run(self._check_connection(config, context, messages))
        except (CancelledError, TimeoutError) as e:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                str(e),
                field="mcp_url",
            ))
        except RuntimeError as e:
            # MCP library cancel scope bug - handle here only
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {e}",
                field="mcp_url",
            ))

        return self._build_report(messages=messages)

    async def _check_connection(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
        messages: List[ValidationMessage],
    ) -> None:
        """
        Async MCP connection check using McpProviderFactory.
        
        Uses anyio.fail_after INSIDE the async function for timeout control.
        """
        try:
            with anyio.fail_after(context.timeout_seconds):
                await self._factory.create_async(config)
            
            # Connection successful
            messages.append(self._info(
                "CONNECTION_OK",
                f"Successfully connected to MCP server at {config.mcp_url}",
                field="mcp_url",
            ))

        except TimeoutError:
            messages.append(self._error(
                ValidationCode.NETWORK_TIMEOUT.value,
                f"Connection timed out after {context.timeout_seconds}s",
                field="mcp_url",
            ))
        except RuntimeError:
            # Let RuntimeError propagate to validate() for handling
            raise
        except Exception as e:
            messages.append(self._error(
                ValidationCode.ENDPOINT_UNREACHABLE.value,
                f"Connection failed: {str(e)}",
                field="mcp_url",
            ))
