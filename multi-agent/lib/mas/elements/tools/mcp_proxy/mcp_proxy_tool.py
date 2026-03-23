from typing import Optional, Type, Any, Dict
from pydantic import BaseModel, HttpUrl
from global_utils.utils.util import validate_arguments
from global_utils.utils.async_bridge import get_async_bridge
from mas.elements.providers.mcp_server_client.mcp_server_client import McpServerClient
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType
from mas.elements.tools.common.base_tool import BaseTool

from global_utils.utils.util import json_schema_model


class McpProxyToolError(Exception):
    """Exception for MCP proxy tool errors"""
    pass


class McpProxyTool(BaseTool):
    """
    A proxy tool that forwards calls to MCP server tools by creating fresh clients per portal.
    This approach eliminates cross-event-loop thread safety issues by avoiding shared state.
    Each tool call creates a new McpServerClient in the current event loop.
    """

    def __init__(
            self,
            mcp_tool_name: str,
            mcp_url: HttpUrl,
            headers: Optional[Dict[str, str]] = None,
            transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ):
        self.name = mcp_tool_name
        self.mcp_tool_name = mcp_tool_name
        self.mcp_url = mcp_url  # Store endpoint instead of client
        self.headers = headers or {}  # Store headers for authentication
        self.transport_type = transport_type  # Store transport protocol
        self._tool_info = None
        self._schema_initialized = False

        # Note: Use create_async() or create_sync() factory methods for full initialization

    async def _ensure_tool_info(self, client: McpServerClient) -> None:
        """
        Fetch the tool's metadata (description + inputSchema) exactly once.
        Uses the provided fresh client from the current event loop.
        """
        if self._tool_info is not None:
            return

        tool_info = await client.get_tool_by_name(self.mcp_tool_name)

        if not tool_info:
            # If the tool isn't found, list all available tools for error context
            available = await client.get_tools()
            raise McpProxyToolError(
                f"MCP tool '{self.mcp_tool_name}' not found. Available tools: {available}"
            )

        # Cache the fetched metadata
        self._tool_info = tool_info
        self.description = tool_info.description
        self.args_schema = tool_info.inputSchema
        self._schema_initialized = True

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Synchronous wrapper—only for use when no event loop is running.
        Otherwise, call `await arun(...)` directly.
        """
        try:
            with get_async_bridge() as bridge:
                return bridge.run(self.arun(*args, **kwargs))
        except Exception as e:
            raise McpProxyToolError(
                f"Synchronous execution failed for '{self.mcp_tool_name}': {e}"
            )

    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """
        Asynchronous entry point. Steps:
          1) Create fresh MCP client in current event loop.
          2) Ensure schema is loaded (only once).
          3) Validate + prepare arguments via Pydantic model.
          4) Call tool using fresh client.
          5) Return the extracted result.
        
        This approach eliminates cross-event-loop thread safety issues.
        """
        # 1) Create fresh client in current event loop/portal with auth headers
        client = McpServerClient(
            mcp_url=self.mcp_url,
            headers=self.headers,
            transport_type=self.transport_type,
        )
        
        # 2) Use the fresh client for all operations
        async with client:
            # 3) Fetch schema once if not already
            if not self._schema_initialized:
                await self._ensure_tool_info(client)

            # 4) Validate + prune arguments
            mcp_args = self._prepare_arguments(kwargs)
            print(f"Executing tool '{self.mcp_tool_name}' with args: {mcp_args}")

            # 5) Call tool using fresh client
            try:
                result = await client.call_tool(self.mcp_tool_name, mcp_args)
                print(f"Tool '{self.mcp_tool_name}' completed successfully")
            except Exception as e:
                # print(f"Tool '{self.mcp_tool_name}' failed: {e}")
                raise McpProxyToolError(f"Failed to call '{self.mcp_tool_name}': {e}")

        # 6) Return the most relevant piece of the result
        return self._extract_result_content(result)

    def _prepare_arguments(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate args against JSON schema.
        """
        if not kwargs or not self.args_schema:
            return kwargs or {}

        validate_arguments(schema=self.get_args_schema_json(), args=kwargs)
        return kwargs

    def _extract_result_content(self, result) -> Any:
        """
        Take whatever `CallToolResult` returned and pick out the most relevant piece.
        Typically MCP returns a `.content` list of TextContent or DataContent objects.
        """
        try:
            if hasattr(result, "content") and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    first = result.content[0]
                    if hasattr(first, "text"):
                        return first.text
                    if hasattr(first, "data"):
                        return first.data
                    return str(first)
                return str(result.content)
            return str(result)
        except Exception:
            return str(result)

    def get_args_schema_json(self) -> Dict[str, Any]:
        """
        Return the raw JSON schema that MCP provided for this tool.
        """
        return self.args_schema

    def get_args_schema_model(self) -> Optional[Type[BaseModel]]:
        """
        Dynamically build a Pydantic model from the MCP JSON schema
        so we can perform argument validation in Python.
        """
        if not self.args_schema:
            return None
        return json_schema_model(self.args_schema, self.name)

    async def refresh_schema(self) -> None:
        """
        Discard the cached schema & description, then re‐fetch them from MCP.
        """
        self._tool_info = None
        self._schema_initialized = False
        self.args_schema = None
        await self._ensure_tool_info()

    async def health_check(self) -> bool:
        """
        Quickly verify that:
          1) a new context enter reconnects if needed
          2) the remote tool still exists
        """
        try:
            async with self.mcp_client:
                info = await self.mcp_client.get_tool_by_name(self.mcp_tool_name)
            return info is not None
        except Exception:
            return False

    def __str__(self) -> str:
        return f"McpProxyTool(name='{self.name}', mcp_tool='{self.mcp_tool_name}')"

    @classmethod
    async def create_async(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ) -> "McpProxyTool":
        """
        Async factory method for creating a fully initialized McpProxyTool.
        
        Args:
            mcp_tool_name: Name of the MCP tool to proxy
            mcp_url: MCP server HTTP endpoint
            headers: Optional HTTP headers for authentication
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            
        Returns:
            Fully initialized McpProxyTool instance
        """
        tool = cls(
            mcp_tool_name, mcp_url,
            headers=headers, transport_type=transport_type,
        )
        
        # Initialize schema using a fresh client with headers
        client = McpServerClient(
            mcp_url=mcp_url, headers=headers,
            transport_type=transport_type,
        )
        async with client:
            await tool._ensure_tool_info(client)
        
        return tool

    @classmethod
    def create_sync(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ) -> "McpProxyTool":
        """
        Sync factory method for creating a fully initialized McpProxyTool.
        Uses AsyncBridge internally to handle the async initialization.
        
        Args:
            mcp_tool_name: Name of the MCP tool to proxy
            mcp_url: MCP server HTTP endpoint
            headers: Optional HTTP headers for authentication
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            
        Returns:
            Fully initialized McpProxyTool instance
        """
        with get_async_bridge() as bridge:
            return bridge.run(cls.create_async(
                mcp_tool_name, mcp_url,
                headers, transport_type=transport_type,
            ))

    @classmethod
    def create_with_cached_schema(
        cls,
        mcp_tool_name: str,
        mcp_url: HttpUrl,
        tool_info,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ) -> "McpProxyTool":
        """
        Create tool with pre-cached schema (no connection needed).
        This is the optimization - tool creation without connection.
        
        Args:
            mcp_tool_name: Name of the MCP tool to proxy
            mcp_url: MCP server HTTP endpoint
            tool_info: Pre-fetched Tool object with schema information
            headers: Optional HTTP headers for authentication
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            
        Returns:
            Fully initialized McpProxyTool instance
        """
        tool = cls(
            mcp_tool_name, mcp_url,
            headers=headers, transport_type=transport_type,
        )
        
        # Use cached tool info
        tool._tool_info = tool_info
        tool.description = tool_info.description or ""
        tool.args_schema = tool_info.inputSchema or {}
        tool._schema_initialized = True
        
        return tool

    def __repr__(self) -> str:
        desc = (self.description[:50] + "...") if self.description else "No description"
        return (
            f"McpProxyTool(name='{self.name}', mcp_tool_name='{self.mcp_tool_name}', "
            f"transport={self.transport_type.value}, "
            f"description='{desc}', endpoint='{self.mcp_url}')"
        )
