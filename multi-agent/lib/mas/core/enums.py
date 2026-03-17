from enum import Enum


class ResourceCategory(str, Enum):
    """Categories of resources in blueprints."""
    LLM = "llms"
    TOOL = "tools"
    RETRIEVER = "retrievers"
    CONDITION = "conditions"
    PROVIDER = "providers"
    NODE = "nodes"
    
    @classmethod
    def plan_categories(cls) -> frozenset:
        """Categories that appear in the final blueprint (plan-referenced)."""
        return frozenset({cls.NODE, cls.CONDITION})
    
    def is_plan_category(self) -> bool:
        """Check if this category is plan-referenced."""
        return self in self.plan_categories()


class SystemNodeType(str, Enum):
    """Node types that stay inline in blueprints (never saved as resources)."""
    USER_QUESTION = "user_question_node"
    FINAL_ANSWER = "final_answer_node"
    
    @classmethod
    def values(cls) -> frozenset:
        """All system node type values as strings."""
        return frozenset(e.value for e in cls)