from typing import Union, Annotated
from pydantic import Field
from mas.elements.providers.mcp_server_client.config import McpProviderConfig

# Union type for backward compatibility with blueprints
ProviderSpec = Annotated[
    Union[
        McpProviderConfig,
    ],
    Field(discriminator="type")
]
