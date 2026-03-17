from abc import ABC, abstractmethod
from typing import Any


class ModuleRunner(ABC):
    @abstractmethod
    def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a module with a unified request/response contract."""

