"""
Temporal client factory.

Provides an async function to connect to the Temporal server
using configuration from AppConfig.

Uses pydantic_data_converter so Temporal natively serializes/deserializes
Pydantic models — no manual model_dump / model_validate needed in
workflow and activity params.

Shared by both inbound (worker) and outbound (executor/submitter)
Temporal adapters.
"""
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from config.app_config import AppConfig
from global_utils.utils.util import get_temporal_url


async def get_temporal_client() -> Client:
    cfg = AppConfig.get_instance()
    return await Client.connect(
        get_temporal_url(),
        namespace=cfg.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
