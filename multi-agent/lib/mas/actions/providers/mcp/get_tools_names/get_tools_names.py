from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field
from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType
from mas.core.enums import ResourceCategory


# Input/Output models for this action
class GetToolsNamesInput(BaseActionInput):
    """Input for MCP tools discovery"""
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


class GetToolsNamesOutput(BaseActionOutput):
    """Output for MCP tools discovery"""
    tool_names: List[str] = []
    total_count: int = 0


class GetToolsNamesAction(BaseAction):
    """
    Discovers available tool names from MCP server.
    
    This action can work with any MCP-compatible element or independently.
    Single Responsibility: Only discovers and returns tool names
    """
    
    uid = "mcp.get_tools_names"
    name = "get_tools_names"
    description = "Retrieve the list of available tool names from the MCP server"
    action_type = ActionType.DISCOVERY
    input_schema = GetToolsNamesInput
    output_schema = GetToolsNamesOutput
    version = "1.0.0"
    tags = {"mcp", "discovery", "tools"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}
    
    def __init__(self, factory: McpProviderFactory = None):
        """
        Initialize action with optional factory injection.
        
        Args:
            factory: McpProviderFactory instance (creates default if not provided)
        """
        super().__init__()
        self._factory = factory or McpProviderFactory()
    
    async def execute(self, input_data: GetToolsNamesInput, 
                     context: Optional[Dict[str, Any]] = None) -> GetToolsNamesOutput:
        """
        Execute tools discovery asynchronously.
        
        Args:
            input_data: Validated discovery input
            context: Optional execution context (element configs, etc.)
            
        Returns:
            Discovery result with tool names and count
        """
        try:
            # Create config from input data
            config = McpProviderConfig(
                mcp_url=input_data.mcp_url,
                bearer_token=input_data.bearer_token,
                transport_type=input_data.transport_type,
                additional_headers=input_data.additional_headers,
            )
            
            # Create provider using factory - fetches tools during initialization
            provider = await self._factory.create_async(config)
            tools = provider.get_tools()
            tool_names = [tool.name for tool in tools]
            
            return GetToolsNamesOutput(
                success=True,
                message=f"Found {len(tool_names)} tools",
                tool_names=tool_names,
                total_count=len(tool_names)
            )
            
        except Exception as e:
            return GetToolsNamesOutput(
                success=False,
                message=f"Failed to retrieve tools: {str(e)}",
                tool_names=[],
                total_count=0
            )
