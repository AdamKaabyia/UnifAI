import threading
from typing import Dict, List, Type, Set, Optional, Tuple
from global_utils.utils.singleton import SingletonMeta
from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import ActionType
from mas.core.enums import ResourceCategory


class ActionRegistry(metaclass=SingletonMeta):
    """
    Registry for all actions, independent of elements.
    Actions are registered by UID and can be discovered by various criteria.
    """
    _lock = threading.RLock()

    def __init__(self) -> None:
        # Map UID -> Action class
        self._actions: Dict[str, Type[BaseAction]] = {}
        # Map action_type -> Set of UIDs
        self._by_type: Dict[ActionType, Set[str]] = {}
        # Map tag -> Set of UIDs
        self._by_tag: Dict[str, Set[str]] = {}
        # Map element tuple (category, type) -> Set of UIDs
        self._by_element: Dict[Tuple[str, str], Set[str]] = {}
        # Map category -> Set of UIDs
        self._by_category: Dict[str, Set[str]] = {}

    def register_action(self, action_cls: Type[BaseAction]) -> None:
        """Register a new action class."""
        with self._lock:
            if action_cls.uid in self._actions:
                raise ValueError(f"Action already registered: {action_cls.uid}")
            
            self._actions[action_cls.uid] = action_cls
            
            # Index by type
            self._by_type.setdefault(action_cls.action_type, set()).add(action_cls.uid)
            
            # Index by tags
            for tag in getattr(action_cls, 'tags', set()):
                self._by_tag.setdefault(tag, set()).add(action_cls.uid)
            
            # Index by element tuples
            for category, element_type in getattr(action_cls, 'elements', set()):
                element_tuple = (category, element_type)
                self._by_element.setdefault(element_tuple, set()).add(action_cls.uid)
                self._by_category.setdefault(category, set()).add(action_cls.uid)

    def get_action(self, uid: str) -> Type[BaseAction]:
        """Get action class by UID."""
        if uid not in self._actions:
            raise KeyError(f"No action registered with UID: {uid}")
        return self._actions[uid]

    def has_action(self, uid: str) -> bool:
        """Check if action is registered by UID."""
        return uid in self._actions

    def get_actions_by_type(self, action_type: ActionType) -> List[Type[BaseAction]]:
        """Get all actions of a specific type."""
        uids = self._by_type.get(action_type, set())
        return [self._actions[uid] for uid in uids]

    def get_actions_by_tag(self, tag: str) -> List[Type[BaseAction]]:
        """Get all actions with a specific tag."""
        uids = self._by_tag.get(tag, set())
        return [self._actions[uid] for uid in uids]

    def get_actions_for_element(self, category: str, element_type: str) -> List[Type[BaseAction]]:
        """Get all actions compatible with an element (category, type)."""
        element_tuple = (category, element_type)
        uids = self._by_element.get(element_tuple, set())
        return [self._actions[uid] for uid in uids]
    
    def get_actions_by_category(self, category: str) -> List[Type[BaseAction]]:
        """Get all actions compatible with a category."""
        uids = self._by_category.get(category, set())
        return [self._actions[uid] for uid in uids]

    def list_all_actions(self) -> List[Type[BaseAction]]:
        """Get all registered actions."""
        return list(self._actions.values())

    def search_actions(self, 
                      action_type: Optional[ActionType] = None,
                      tags: Optional[Set[str]] = None,
                      category: Optional[str] = None,
                      element_type: Optional[str] = None) -> List[Type[BaseAction]]:
        """Search actions by multiple criteria."""
        result_uids = set(self._actions.keys())
        
        if action_type:
            result_uids &= self._by_type.get(action_type, set())
        
        if tags:
            for tag in tags:
                result_uids &= self._by_tag.get(tag, set())
        
        if category and element_type:
            element_tuple = (category, element_type)
            result_uids &= self._by_element.get(element_tuple, set())
        elif category:
            result_uids &= self._by_category.get(category, set())
        
        return [self._actions[uid] for uid in result_uids]

    def get_registry_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        return {
            "total_actions": len(self._actions),
            "action_types": len(self._by_type),
            "tags": len(self._by_tag),
            "elements": len(self._by_element),
            "categories": len(self._by_category)
        }

    def auto_discover(self) -> None:
        """
        Discover all BaseAction subclasses and register them automatically.
        """
        from .action_discoverer import ActionDiscoverer
        
        discoverer = ActionDiscoverer()
        for action_cls in discoverer.discover():
            try:
                self.register_action(action_cls)
            except ValueError as e:
                # Action already registered, skip
                pass
