from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import SshExecToolConfig
from ..ssh_exec_factory import SshExecToolFactory
from ..identifiers import Identifier, META
from ..validator import SshExecToolValidator
from mas.elements.tools.common.card_builder import ToolCardBuilder


class SshExecToolElementSpec(BaseElementSpec):
    """Element specification for SSH Exec Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = SshExecToolConfig
    factory_cls = SshExecToolFactory
    tags = META.tags
    validator_cls = SshExecToolValidator
    card_builder_cls = ToolCardBuilder
