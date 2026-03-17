"""
Tool for listing adjacent nodes.
"""

from typing import Dict, Any, Callable, List
from pydantic import BaseModel
from mas.elements.tools.common.base_tool import BaseTool
from mas.elements.nodes.common.agent.constants import ToolNames

class ListAdjacentNodeArgs(BaseModel):
    pass


class ListAdjacentNodesTool(BaseTool):
    """List all adjacent nodes with their capabilities."""
    
    name = ToolNames.TOPOLOGY_LIST_ADJACENT
    description = "Get a list of all adjacent nodes with their capabilities and skills"
    args_schema = ListAdjacentNodeArgs
    
    def __init__(self, get_adjacent_nodes: Callable[[], Dict[str, Any]]):
        self._get_adjacent_nodes = get_adjacent_nodes
    
    def run(self, **kwargs) -> Dict[str, Any]:
        """List adjacent nodes."""
        adjacent_nodes = self._get_adjacent_nodes()
        
        if not adjacent_nodes:
            return {
                "adjacent_count": 0,
                "nodes": []
            }
        
        nodes_info = []
        for uid, card in adjacent_nodes.items():
            node_info = {
                "uid": uid,
                "name": card.name,
                "type": card.type_key,
                "description": card.description,
                "capabilities": [cap.name for cap in card.capabilities] if card.capabilities else [],
                "skills_summary": self._summarize_skills(card.skills)
            }
            nodes_info.append(node_info)
        
        return {
            "adjacent_count": len(adjacent_nodes),
            "nodes": nodes_info
        }
    
    def _summarize_skills(self, skills: List) -> Dict[str, int]:
        """Summarize skills by counting total."""
        return {"total_skills": len(skills)}
