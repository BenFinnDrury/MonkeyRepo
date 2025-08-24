from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import Monkey
from ..storage.base import BaseStorage


class MonkeyRegistryService:
    """orchestrates validation, uniqueness rules, and persistence"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage

    # helpers ----------------------------------------------------------
    def _ensure_unique_name_species(self, name: str, species: str, exclude_id: Optional[str] = None) -> None:
        existing = self.storage.find_by_name_species(name, species)
        if existing and existing.get("monkey_id") != exclude_id:
            raise ValueError("duplicate name within species is not allowed")

    # crud -------------------------------------------------------------
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # validate via model and enforce uniqueness
        temp = Monkey(**data)  # may raise valueerror
        self._ensure_unique_name_species(temp.name, temp.species.value)
        return self.storage.create(temp.to_dict())

    def get(self, monkey_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get(monkey_id)

    def update(self, monkey_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.storage.get(monkey_id)
        if not current:
            return None
        # re-validate by applying updates through the model
        model = Monkey.from_dict(current)
        model.apply_updates(updates)
        # enforce uniqueness with potential new name/species, excluding self
        self._ensure_unique_name_species(model.name, model.species.value, exclude_id=monkey_id)
        # persist the full record to keep timestamps consistent
        return self.storage.update(monkey_id, model.to_dict())

    def delete(self, monkey_id: str) -> bool:
        return self.storage.delete(monkey_id)

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.storage.list(filters)

    def search(self, query: str) -> List[Dict[str, Any]]:
        return self.storage.search(query)