from typing import Union, Annotated
from pydantic import Field
from .threshold.config import ThresholdConditionConfig
from .router_direct.config import RouterDirectConditionConfig
from .router_boolean.config import RouterBooleanConditionConfig

ConditionSpec = Annotated[
    Union[
        ThresholdConditionConfig,
        RouterDirectConditionConfig,
        RouterBooleanConditionConfig,
    ],
    Field(discriminator="type")
]
