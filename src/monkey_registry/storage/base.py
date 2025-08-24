from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Protocol


class BaseStorage(Protocol):
    """storage interface to support swapping json ↔ dynamodb later"""

    def create(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """persist a new item and return it"""
        ...

    def get(self, monkey_id: str) -> Optional[Dict[str, Any]]:
        """fetch by id or return none"""
        ...

    def update(self, monkey_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """apply updates and return the updated record or none"""
        ...

    def delete(self, monkey_id: str) -> bool:
        """delete by id; return success flag"""
        ...

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """list with optional filters (name/species)"""
        ...

    def search(self, query: str) -> List[Dict[str, Any]]:
        """case-insensitive search across name and species"""
        ...

    def find_by_name_species(self, name: str, species: str) -> Optional[Dict[str, Any]]:
        """helper used for uniqueness check in the service layer"""
        ...