from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        pass
