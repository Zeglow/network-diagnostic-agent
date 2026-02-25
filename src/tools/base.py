from abc import ABC, abstractmethod

class BaseTool(ABC):
    
    @abstractmethod
    def run(self, target: str) -> dict:
        """Every tool must implement this method"""
        pass