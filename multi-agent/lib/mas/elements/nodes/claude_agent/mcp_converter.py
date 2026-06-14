"""
Converts MAS McpProvider instances to Claude SDK mcp_servers format.

Calls provider.get_tools() to get ONLY the user-selected tools,
then wraps them as in-process MCP servers (type "sdk") so
the Claude SDK sees exactly the tools the user chose —
nothing more.
"""

from typing import Any, Dict, List
from urllib.parse import urlparse

from mcp.server import Server as McpServer
from mcp import types as mcp_types

from mas.elements.providers.mcp_server_client.mcp_provider import McpProvider


def convert_providers(
    providers: List[McpProvider],
) -> Dict[str, Dict[str, Any]]:
    """Convert MAS McpProvider instances to Claude SDK mcp_servers format.

    For each provider, calls provider.get_tools() (returns only the
    user-selected tools) and wraps them in a lightweight in-process
    MCP Server. The SDK connects to this proxy — not the remote server
    directly — so it only discovers the selected tools.
    """
    servers: Dict[str, Dict[str, Any]] = {}
    for provider in providers:
        name = _derive_server_name(provider, servers)
        servers[name] = _build_proxy_server(name, provider)
    return servers


def _build_proxy_server(
    name: str, provider: McpProvider
) -> Dict[str, Any]:
    """In-process MCP server exposing only the user-selected tools."""
    selected_tools = provider.get_tools()
    tool_map = {tool.name: tool for tool in selected_tools}

    server = McpServer(name=name)

    @server.list_tools()
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=tool.name,
                description=tool.description or "",
                inputSchema=tool.get_args_schema_json() or {"type": "object"},
            )
            for tool in tool_map.values()
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[mcp_types.TextContent]:
        tool = tool_map.get(name)
        if not tool:
            return [mcp_types.TextContent(type="text", text=f"Unknown tool: {name}")]
        result = await tool.arun(**arguments)
        return [mcp_types.TextContent(type="text", text=str(result))]

    return {"type": "sdk", "name": name, "instance": server}


def _derive_server_name(
    provider: McpProvider, existing: Dict[str, Any]
) -> str:
    hostname = urlparse(str(provider.mcp_url)).hostname or "mcp-server"
    name = hostname
    counter = 2
    while name in existing:
        name = f"{hostname}-{counter}"
        counter += 1
    return name
