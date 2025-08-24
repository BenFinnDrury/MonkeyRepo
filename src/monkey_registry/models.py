from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class Species(str, Enum):
    """valid monkey species"""

    CAPUCHIN = "capuchin"
    MACAQUE = "macaque"
    MARMOSET = "marmoset"
    HOWLER = "howler"


# helpers ---------------------------------------------------------------

def _iso_now() -> str:
    # return an iso8601 timestamp with seconds precision
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    # generate a short stable id (uuid4 hex, 8 chars)
    return f"monkey_{uuid.uuid4().hex[:8]}"


# validation ------------------------------------------------------------

def validate_name(name: str) -> None:
    # name required, trimmed length 2-40
    if name is None:
        raise ValueError("name is required")
    cleaned = name.strip()
    if not (2 <= len(cleaned) <= 40):
        raise ValueError("name must be 2-40 characters")


def validate_species(species: str | Species) -> Species:
    # map strings to enum and validate
    if isinstance(species, Species):
        return species
    try:
        return Species(species.lower())
    except Exception as e:
        raise ValueError("species must be one of: capuchin, macaque, marmoset, howler") from e


def validate_age(age_years: int, species: Species) -> None:
    # age must be 0-45 inclusive; marmoset cap 22
    if not isinstance(age_years, int):
        raise ValueError("age_years must be an integer")
    if age_years < 0 or age_years > 45:
        raise ValueError("age_years must be between 0 and 45")
    if species == Species.MARMOSET and age_years > 22:
        raise ValueError("marmoset age must be ≤ 22")


@dataclass
class Monkey:
    """monkey data model with basic validation and (de)serialization"""

    name: str
    species: Species | str
    age_years: int
    favourite_fruit: str
    last_checkup_at: Optional[str] = None  # iso datetime; optional

    monkey_id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_iso_now)
    updated_at: str = field(default_factory=_iso_now)

    # normalize + validate on init
    def __post_init__(self):
        validate_name(self.name)
        self.species = validate_species(self.species)
        validate_age(self.age_years, self.species)
        # simple check for last_checkup_at format if provided
        if self.last_checkup_at:
            try:
                # we only verify it parses; store as given string
                datetime.fromisoformat(self.last_checkup_at.replace("Z", "+00:00"))
            except Exception as e:
                raise ValueError("last_checkup_at must be iso8601") from e

    # update utility used by service layer
    def apply_updates(self, updates: Dict[str, Any]) -> None:
        # apply only known fields
        for key in ["name", "species", "age_years", "favourite_fruit", "last_checkup_at"]:
            if key in updates and updates[key] is not None:
                setattr(self, key, updates[key])
        # re-normalize + re-validate after changes
        validate_name(self.name)
        self.species = validate_species(self.species)
        validate_age(self.age_years, self.species)
        self.updated_at = _iso_now()

    # serialization helpers -------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "monkey_id": self.monkey_id,
            "name": self.name.strip(),
            "species": self.species.value if isinstance(self.species, Species) else str(self.species),
            "age_years": self.age_years,
            "favourite_fruit": self.favourite_fruit,
            "last_checkup_at": self.last_checkup_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Monkey":
        # construct from persisted dict (id/timestamps may already exist)
        m = cls(
            name=data["name"],
            species=data["species"],
            age_years=int(data["age_years"]),
            favourite_fruit=data.get("favourite_fruit", ""),
            last_checkup_at=data.get("last_checkup_at"),
        )
        if "monkey_id" in data:
            m.monkey_id = data["monkey_id"]
        if "created_at" in data:
            m.created_at = data["created_at"]
        if "updated_at" in data:
            m.updated_at = data["updated_at"]
        return m