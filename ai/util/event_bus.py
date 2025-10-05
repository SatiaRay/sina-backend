from typing import Dict, List, Callable
from enum import Enum

class VectorStoreEvent(Enum):
    COLLECTION_MODIFIED = "collection_modified"
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_UPDATED = "document_updated"

class EventBus:
    _instance = None
    _subscribers: Dict[VectorStoreEvent, List[Callable]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            # Initialize subscribers for each event type
            for event in VectorStoreEvent:
                cls._subscribers[event] = []
        return cls._instance

    def subscribe(self, event: VectorStoreEvent, callback: Callable):
        """Subscribe to an event"""
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)

    def unsubscribe(self, event: VectorStoreEvent, callback: Callable):
        """Unsubscribe from an event"""
        if event in self._subscribers:
            self._subscribers[event].remove(callback)

    def publish(self, event: VectorStoreEvent, data: dict = None):
        """Publish an event to all subscribers"""
        if event in self._subscribers:
            for callback in self._subscribers[event]:
                callback(data)

# Global event bus instance
event_bus = EventBus() 