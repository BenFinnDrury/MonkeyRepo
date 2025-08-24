from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseStorage


class JsonStorage(BaseStorage):
    """simple json file storage for offline development"""

    def __init__(self, file_path: Optional[str] = None):
        # allow overriding via env var; default to data/monkeys.json
        default_path = os.environ.get("MONKEY_DB_PATH", "data/monkeys.json")
        self.path = Path(file_path or default_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    # internal helpers -------------------------------------------------
    def _load_all(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            # if file is corrupted, treat as empty list
            return []

    def _save_all(self, items: List[Dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # interface methods -----------------------------------------------
    def create(self, item: Dict[str, Any]) -> Dict[str, Any]:
        items = self._load_all()
        # prevent duplicate ids
        if any(it.get("monkey_id") == item.get("monkey_id") for it in items):
            raise ValueError("monkey_id already exists")
        items.append(item)
        self._save_all(items)
        return item

    def get(self, monkey_id: str) -> Optional[Dict[str, Any]]:
        items = self._load_all()
        for it in items:
            if it.get("monkey_id") == monkey_id:
                return it
        return None

    def update(self, monkey_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        items = self._load_all()
        updated = None
        for idx, it in enumerate(items):
            if it.get("monkey_id") == monkey_id:
                # apply only provided keys
                it.update({k: v for k, v in updates.items() if v is not None})
                updated = it
                items[idx] = it
                break
        if updated is not None:
            self._save_all(items)
        return updated

    def delete(self, monkey_id: str) -> bool:
        items = self._load_all()
        new_items = [it for it in items if it.get("monkey_id") != monkey_id]
        if len(new_items) == len(items):
            return False
        self._save_all(new_items)
        return True

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        items = self._load_all()
        if not filters:
            return items
        name = (filters.get("name") or "").strip().lower()
        species = (filters.get("species") or "").strip().lower()
        out = []
        for it in items:
            ok = True
            if name:
                ok = ok and (name in str(it.get("name", "")).lower())
            if species:
                ok = ok and (species == str(it.get("species", "")).lower())
            if ok:
                out.append(it)
        return out

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return []
        items = self._load_all()
        return [it for it in items if q in str(it.get("name", "")).lower() or q in str(it.get("species", "")).lower()]

    def find_by_name_species(self, name: str, species: str) -> Optional[Dict[str, Any]]:
        n = (name or "").strip().lower()
        s = (species or "").strip().lower()
        for it in self._load_all():
            if n == str(it.get("name", "")).strip().lower() and s == str(it.get("species", "")).strip().lower():
                return it
        return None