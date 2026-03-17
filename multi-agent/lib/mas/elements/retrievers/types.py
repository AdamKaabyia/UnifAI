from typing import Union, Annotated
from pydantic import Field
from mas.elements.retrievers.docs_rag.config import DocsRagRetrieverConfig
from mas.elements.retrievers.slack.config import SlackRetrieverConfig

# Union type for backward compatibility with blueprints
RetrieversSpec = Annotated[
    Union[
        DocsRagRetrieverConfig,
        SlackRetrieverConfig,
    ],
    Field(discriminator="type")
]
