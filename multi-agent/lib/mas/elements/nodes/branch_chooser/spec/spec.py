from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import BranchChooserNodeConfig
from ..branch_chooser_node_factory import BranchChooserNodeFactory
from ..branch_chooser import BranchChooserNode
from ..identifiers import Identifier, META


class BranchChooserNodeElementSpec(BaseElementSpec):
    """Element specification for Branch Chooser Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = BranchChooserNodeConfig
    factory_cls = BranchChooserNodeFactory
    reads = BranchChooserNode.total_reads()
    writes = BranchChooserNode.total_writes()
    tags = META.tags