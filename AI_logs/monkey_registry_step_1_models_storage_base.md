# step 1 code: core model + storage interface

> files below are meant to be copied into your existing structure:
>
> - `src/monkey_registry/models.py`
> - `src/monkey_registry/storage/base.py`

---

## src/monkey\_registry/models.py

```python
# all comments in lowercase to match user preference

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
```

---

## src/monkey\_registry/storage/base.py

```python
# all comments in lowercase

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
```



---

## sanity check – paste in terminal

```bash
python - <<'PY'
from monkey_registry.models import Monkey, Species, validate_age
m = Monkey(name="Luna", species="marmoset", age_years=2, favourite_fruit="mango")
print("ok:", m.to_dict()["species"], m.to_dict()["name"])
try:
    validate_age(23, Species.MARMOSET)
except Exception as e:
    print("marmoset cap works:", type(e).__name__)
PY
```

## sanity check – paste in pycharm python console

```python
# all comments in lowercase
from monkey_registry.models import Monkey, Species, validate_age
m = Monkey(name="Luna", species="marmoset", age_years=2, favourite_fruit="mango")
print("ok:", m.to_dict()["species"], m.to_dict()["name"])
try:
    validate_age(23, Species.MARMOSET)
except Exception as e:
    print("marmoset cap works:", type(e).__name__)
```



# step 2 code: local json storage

> files below are meant to be copied into your existing structure:
>
> - `src/monkey_registry/storage/json_store.py`
> - `src/monkey_registry/storage/__init__.py` (small export helper)

---

## src/monkey\_registry/storage/json\_store.py

```python
# all comments in lowercase

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
```

---

## src/monkey\_registry/storage/**init**.py

```python
# all comments in lowercase

from .json_store import JsonStorage  # convenience re-export
```

---

## sanity check – storage smoke (paste in terminal)

```bash
python - <<'PY'
from monkey_registry.models import Monkey
from monkey_registry.storage.json_store import JsonStorage

store = JsonStorage()  # uses data/monkeys.json by default

m = Monkey(name="luna", species="marmoset", age_years=2, favourite_fruit="mango")
created = store.create(m.to_dict())
print("created:", created["monkey_id"], created["name"], created["species"]) 

fetched = store.get(created["monkey_id"]) 
print("fetched:", fetched["name"]) 

print("all count:", len(store.list()))
print("search marmoset:", len(store.search("marmo")))
PY
```

### if your terminal prints the snippet instead of running it

- make sure the **very last line** is only `PY` with no spaces.
- run it in the **terminal** panel, not in the run config.

### one-line alternative (works everywhere)

```bash
python -c "from monkey_registry.models import Monkey; from monkey_registry.storage.json_store import JsonStorage; s=JsonStorage(); m=Monkey(name='luna', species='marmoset', age_years=2, favourite_fruit='mango'); c=s.create(m.to_dict()); print('created:', c['monkey_id'], c['name'], c['species']); f=s.get(c['monkey_id']); print('fetched:', f['name']); print('all count:', len(s.list())); print('search marmoset:', len(s.search('marmo')))"
```

## expected output (first run)

```
created: monkey_XXXXXXXX luna marmoset
fetched: luna
all count: 1
search marmoset: 1
```



# step 3 code: service layer (domain rules)

> copy into `src/monkey_registry/services/registry.py`

````python
# all comments in lowercase

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
        # fix: use enum value, not str(enum) which yields 'Species.MARMOSET'
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
        # fix: use enum value for uniqueness check
        self._ensure_unique_name_species(model.name, model.species.value, exclude_id=monkey_id)
        # persist the full record to keep timestamps consistent
        return self.storage.update(monkey_id, model.to_dict())

    def delete(self, monkey_id: str) -> bool:
        return self.storage.delete(monkey_id)

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.storage.list(filters)

    def search(self, query: str) -> List[Dict[str, Any]]:
        return self.storage.search(query)
```python
# all comments in lowercase

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
        self._ensure_unique_name_species(temp.name, str(temp.species))
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
        self._ensure_unique_name_species(model.name, str(model.species), exclude_id=monkey_id)
        # persist the full record to keep timestamps consistent
        return self.storage.update(monkey_id, model.to_dict())

    def delete(self, monkey_id: str) -> bool:
        return self.storage.delete(monkey_id)

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.storage.list(filters)

    def search(self, query: str) -> List[Dict[str, Any]]:
        return self.storage.search(query)
````

---

# step 4 code: minimal cli (click + rich)

> copy into `src/monkey_registry/cli.py` and `src/monkey_registry/app.py`

## src/monkey\_registry/cli.py

```python
# all comments in lowercase

from __future__ import annotations

import os
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .services.registry import MonkeyRegistryService
from .storage import JsonStorage

console = Console()


def get_registry(db_path: Optional[str] = None) -> MonkeyRegistryService:
    # allow override via flag or env var; default data/monkeys.json
    path = db_path or os.environ.get("MONKEY_DB_PATH") or "data/monkeys.json"
    store = JsonStorage(file_path=path)
    return MonkeyRegistryService(store)


@click.group(help="monkey registry cli")
@click.option("--db", "db_path", default=None, help="path to json db file (default: data/monkeys.json)")
@click.pass_context
def cli(ctx: click.Context, db_path: Optional[str]):
    # attach the registry to context so subcommands can use it
    ctx.obj = {"registry": get_registry(db_path)}


@cli.command("create", help="create a new monkey")
@click.option("--name", required=True, help="name (2-40 chars)")
@click.option("--species", required=True, type=click.Choice(["capuchin", "macaque", "marmoset", "howler"], case_sensitive=False))
@click.option("--age", "age_years", required=True, type=int, help="age in years (0-45; marmoset ≤ 22)")
@click.option("--fruit", "favourite_fruit", required=True, help="favourite fruit")
@click.option("--last-checkup", "last_checkup_at", required=False, help="iso datetime, optional")
@click.pass_context
def create_cmd(ctx: click.Context, name: str, species: str, age_years: int, favourite_fruit: str, last_checkup_at: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    try:
        created = reg.create({
            "name": name,
            "species": species,
            "age_years": age_years,
            "favourite_fruit": favourite_fruit,
            "last_checkup_at": last_checkup_at,
        })
        console.print({k: created[k] for k in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]})
    except Exception as e:
        console.print(f"error: {e}", style="bold red")
        raise SystemExit(1)


@cli.command("get", help="get a monkey by id")
@click.argument("monkey_id")
@click.pass_context
def get_cmd(ctx: click.Context, monkey_id: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    item = reg.get(monkey_id)
    if not item:
        console.print("not found", style="yellow")
        raise SystemExit(1)
    console.print(item)


@cli.command("update", help="update a monkey")
@click.argument("monkey_id")
@click.option("--name")
@click.option("--species", type=click.Choice(["capuchin", "macaque", "marmoset", "howler"], case_sensitive=False))
@click.option("--age", "age_years", type=int)
@click.option("--fruit", "favourite_fruit")
@click.option("--last-checkup", "last_checkup_at")
@click.pass_context
def update_cmd(ctx: click.Context, monkey_id: str, name: Optional[str], species: Optional[str], age_years: Optional[int], favourite_fruit: Optional[str], last_checkup_at: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    try:
        updated = reg.update(monkey_id, {
            "name": name,
            "species": species,
            "age_years": age_years,
            "favourite_fruit": favourite_fruit,
            "last_checkup_at": last_checkup_at,
        })
        if not updated:
            console.print("not found", style="yellow")
            raise SystemExit(1)
        console.print({k: updated[k] for k in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]})
    except Exception as e:
        console.print(f"error: {e}", style="bold red")
        raise SystemExit(1)


@cli.command("delete", help="delete a monkey by id")
@click.argument("monkey_id")
@click.pass_context
def delete_cmd(ctx: click.Context, monkey_id: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    ok = reg.delete(monkey_id)
    console.print("deleted" if ok else "not found")
    if not ok:
        raise SystemExit(1)


@cli.command("list", help="list monkeys (optional filters)")
@click.option("--name", default=None)
@click.option("--species", default=None)
@click.pass_context
def list_cmd(ctx: click.Context, name: Optional[str], species: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    rows = reg.list({"name": name, "species": species})
    table = Table(title="monkeys")
    for col in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]:
        table.add_column(col)
    for r in rows:
        table.add_row(r.get("monkey_id",""), r.get("name",""), str(r.get("species","")), str(r.get("age_years","")), r.get("favourite_fruit",""))
    console.print(table)


@cli.command("search", help="search by name or species")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    rows = reg.search(query)
    console.print(f"found {len(rows)} result(s)")
    for r in rows:
        console.print({k: r[k] for k in ["monkey_id", "name", "species", "age_years"]})
```

## src/monkey\_registry/app.py

````python
# all comments in lowercase

from __future__ import annotations

# use absolute import so it works whether run as a script or module
from monkey_registry.cli import cli  # note: absolute import


if __name__ == "__main__":
    # delegate to click cli
    cli()
```python
# all comments in lowercase

from __future__ import annotations

from .cli import cli


if __name__ == "__main__":
    # delegate to click cli
    cli()
````

---

## sanity checks – cli

### 0) ensure python can see `src`

```bash
export PYTHONPATH=src
```

### 1) create

```bash
python src/monkey_registry/app.py create --name luna --species marmoset --age 2 --fruit mango
```

expected: prints a dict with `monkey_id`, `name`, `species`, `age_years`, `favourite_fruit`.

### 2) list

```bash
python src/monkey_registry/app.py list
```

expected: a table with at least one row.

### 3) duplicate check (should error)

```bash
python src/monkey_registry/app.py create --name luna --species marmoset --age 3 --fruit banana
```

expected: `error: duplicate name within species is not allowed` and exit code 1.

### 4) search

```bash
python src/monkey_registry/app.py search marmoset
```

expected: `found 1 result(s)` (or more if you added others).

### 5) update (e.g., change fruit)

```bash
# replace <id> with the printed monkey_id
python src/monkey_registry/app.py update <id> --fruit "pineapple"
```

expected: prints the updated record with `favourite_fruit` changed.

### 6) delete

```bash
python src/monkey_registry/app.py delete <id>
```

expected: prints `deleted`.



# step 5 code: tests to lock rules (offline)

> add these files, then run `pytest -q` from project root (with `PYTHONPATH=src` not required if you have `pytest.ini` set as below).

---

## pytest.ini (confirm or create at project root)

```ini
[pytest]
asyncio_mode = auto
pythonpath = src
testpaths = tests
```

---

## tests/test\_validation.py

```python
# all comments in lowercase

import pytest

from monkey_registry.models import Monkey, Species


def test_marmoset_age_cap_rejected():
    # marmoset older than 22 should raise
    with pytest.raises(ValueError):
        Monkey(name="oldie", species=Species.MARMOSET, age_years=23, favourite_fruit="banana")


def test_valid_monkey_constructs():
    m = Monkey(name="luna", species="marmoset", age_years=2, favourite_fruit="mango")
    d = m.to_dict()
    assert d["name"] == "luna"
    assert d["species"] == "marmoset"
    assert d["age_years"] == 2
```

---

## tests/test\_cli\_smoke.py

```python
# all comments in lowercase

from pathlib import Path
from click.testing import CliRunner

from monkey_registry.cli import cli


def test_cli_crud_smoke(tmp_path: Path):
    # use an isolated temp json file so we don't touch real data
    dbfile = tmp_path / "monkeys.json"
    env = {"MONKEY_DB_PATH": str(dbfile)}

    runner = CliRunner()

    # create
    res = runner.invoke(cli, ["create", "--name", "luna", "--species", "marmoset", "--age", "2", "--fruit", "mango"], env=env)
    assert res.exit_code == 0, res.output

    # duplicate should fail (same name within same species)
    res2 = runner.invoke(cli, ["create", "--name", "luna", "--species", "marmoset", "--age", "3", "--fruit", "banana"], env=env)
    assert res2.exit_code != 0
    assert "duplicate name" in res2.output.lower()

    # different species with same name should succeed
    res3 = runner.invoke(cli, ["create", "--name", "luna", "--species", "macaque", "--age", "3", "--fruit", "banana"], env=env)
    assert res3.exit_code == 0, res3.output

    # list and search should find items
    res_list = runner.invoke(cli, ["list"], env=env)
    assert res_list.exit_code == 0 and "luna" in res_list.output

    res_search = runner.invoke(cli, ["search", "marmo"], env=env)
    assert res_search.exit_code == 0 and "found" in res_search.output.lower()
```

---

## sanity checks – run tests

### 1) run pytest

```bash
python -m pytest -q
```

**expect:**

```
2 passed, 0 skipped in X.XXs    # if you only added test_validation
# or
3 passed, 0 skipped in X.XXs    # if both tests present
```

### 2) confirm isolation

- after tests, your real `data/monkeys.json` should be unchanged because tests use a temp file via `MONKEY_DB_PATH`.

---

when this is green, you’ll have:

- model + storage + service + cli working offline
- tests proving the age cap and uniqueness

confirm the `pytest -q` result and we’ll proceed to the final offline step: prepare the repo files (`.gitignore`, `.env.example`, README/process logs), then clone and push. no aws/dynamodb yet unless you want to stretch after the push.



# step 6 code: switchable aws dynamodb storage (tidy-up before push)

> we will keep json as default and add a `ddb` option. no secrets in code. copy the new file and replace `cli.py` with the updated version below.

---

## src/monkey\_registry/storage/dynamodb\_store.py

```python
# all comments in lowercase

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr


class DynamoStorage:
    """dynamodb implementation of the storage interface
    uses a simple key design: pk = sk = f"MONKEY#{monkey_id}"
    other attributes stored as plain types; includes lowercase helper fields for filtering
    """

    def __init__(self, table_name: Optional[str] = None, region: Optional[str] = None):
        self.region = region or os.environ.get("AWS_REGION", "eu-west-1")
        self.table_name = table_name or os.environ.get("DDB_TABLE", "assessment-users")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)

    # helpers ----------------------------------------------------------
    @staticmethod
    def _pk(monkey_id: str) -> str:
        return f"MONKEY#{monkey_id}"

    @staticmethod
    def _clean(d: Dict[str, Any]) -> Dict[str, Any]:
        # remove none values (dynamodb can store empty strings now, but we avoid none)
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def _iso_now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _to_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # ensure helper fields for case-insensitive filters
        name = str(data.get("name", ""))
        species = str(data.get("species", ""))
        item = {
            "PK": self._pk(data["monkey_id"]),
            "SK": self._pk(data["monkey_id"]),
            "entity": "MONKEY",
            **self._clean(data),
            "name_lc": name.strip().lower(),
            "species_lc": species.strip().lower(),
        }
        return item

    @staticmethod
    def _from_item(item: Dict[str, Any]) -> Dict[str, Any]:
        # strip dynamo-only fields
        out = {k: v for k, v in item.items() if k not in {"PK", "SK", "entity", "name_lc", "species_lc"}}
        return out

    # interface methods -----------------------------------------------
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        item = self._to_item(data)
        # prevent overwriting existing id
        self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
        return self._from_item(item)

    def get(self, monkey_id: str) -> Optional[Dict[str, Any]]:
        res = self.table.get_item(Key={"PK": self._pk(monkey_id), "SK": self._pk(monkey_id)})
        it = res.get("Item")
        return self._from_item(it) if it else None

    def update(self, monkey_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # read-modify-write for simplicity (small scale)
        current = self.get(monkey_id)
        if not current:
            return None
        merged = {**current, **{k: v for k, v in updates.items() if v is not None}}
        merged["updated_at"] = self._iso_now()
        item = self._to_item(merged)
        self.table.put_item(Item=item)
        return self._from_item(item)

    def delete(self, monkey_id: str) -> bool:
        self.table.delete_item(Key={"PK": self._pk(monkey_id), "SK": self._pk(monkey_id)})
        # we assume delete succeeds if no exception
        return True

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # use scan + filters (ok for assessment scale). a gsi would be better for production.
        fe = Attr("entity").eq("MONKEY")
        if filters:
            name = (filters.get("name") or "").strip().lower()
            species = (filters.get("species") or "").strip().lower()
            if name:
                fe = fe & Attr("name_lc").contains(name)
            if species:
                fe = fe & Attr("species_lc").eq(species)
        res = self.table.scan(FilterExpression=fe)
        items = res.get("Items", [])
        return [self._from_item(it) for it in items]

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return []
        fe = (Attr("entity").eq("MONKEY")) & (
            Attr("name_lc").contains(q) | Attr("species_lc").contains(q)
        )
        res = self.table.scan(FilterExpression=fe)
        return [self._from_item(it) for it in res.get("Items", [])]

    def find_by_name_species(self, name: str, species: str) -> Optional[Dict[str, Any]]:
        fe = (
            Attr("entity").eq("MONKEY") &
            Attr("name_lc").eq((name or "").strip().lower()) &
            Attr("species_lc").eq((species or "").strip().lower())
        )
        res = self.table.scan(FilterExpression=fe)
        items = res.get("Items", [])
        return self._from_item(items[0]) if items else None
```

---

## src/monkey\_registry/cli.py (replace with this version)

```python
# all comments in lowercase

from __future__ import annotations

import os
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .services.registry import MonkeyRegistryService
from .storage import JsonStorage
from .storage.dynamodb_store import DynamoStorage

console = Console()


def get_registry(db_path: Optional[str] = None, backend: Optional[str] = None) -> MonkeyRegistryService:
    # backend resolution order: flag > env BACKEND > default json
    backend = (backend or os.environ.get("BACKEND") or "json").lower()
    if backend in ("ddb", "dynamodb"):
        store = DynamoStorage(table_name=os.environ.get("DDB_TABLE"), region=os.environ.get("AWS_REGION"))
    else:
        path = db_path or os.environ.get("MONKEY_DB_PATH") or "data/monkeys.json"
        store = JsonStorage(file_path=path)
    return MonkeyRegistryService(store)


@click.group(help="monkey registry cli")
@click.option("--db", "db_path", default=None, help="path to json db file (default: data/monkeys.json)")
@click.option("--backend", type=click.Choice(["json", "ddb"], case_sensitive=False), default=None, help="storage backend")
@click.pass_context
def cli(ctx: click.Context, db_path: Optional[str], backend: Optional[str]):
    # attach the registry to context so subcommands can use it
    ctx.obj = {"registry": get_registry(db_path, backend)}


@cli.command("create", help="create a new monkey")
@click.option("--name", required=True, help="name (2-40 chars)")
@click.option("--species", required=True, type=click.Choice(["capuchin", "macaque", "marmoset", "howler"], case_sensitive=False))
@click.option("--age", "age_years", required=True, type=int, help="age in years (0-45; marmoset ≤ 22)")
@click.option("--fruit", "favourite_fruit", required=True, help="favourite fruit")
@click.option("--last-checkup", "last_checkup_at", required=False, help="iso datetime, optional")
@click.pass_context
def create_cmd(ctx: click.Context, name: str, species: str, age_years: int, favourite_fruit: str, last_checkup_at: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    try:
        created = reg.create({
            "name": name,
            "species": species,
            "age_years": age_years,
            "favourite_fruit": favourite_fruit,
            "last_checkup_at": last_checkup_at,
        })
        console.print({k: created[k] for k in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]})
    except Exception as e:
        console.print(f"error: {e}", style="bold red")
        raise SystemExit(1)


@cli.command("get", help="get a monkey by id")
@click.argument("monkey_id")
@click.pass_context
def get_cmd(ctx: click.Context, monkey_id: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    item = reg.get(monkey_id)
    if not item:
        console.print("not found", style="yellow")
        raise SystemExit(1)
    console.print(item)


@cli.command("update", help="update a monkey")
@click.argument("monkey_id")
@click.option("--name")
@click.option("--species", type=click.Choice(["capuchin", "macaque", "marmoset", "howler"], case_sensitive=False))
@click.option("--age", "age_years", type=int)
@click.option("--fruit", "favourite_fruit")
@click.option("--last-checkup", "last_checkup_at")
@click.pass_context
def update_cmd(ctx: click.Context, monkey_id: str, name: Optional[str], species: Optional[str], age_years: Optional[int], favourite_fruit: Optional[str], last_checkup_at: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    try:
        updated = reg.update(monkey_id, {
            "name": name,
            "species": species,
            "age_years": age_years,
            "favourite_fruit": favourite_fruit,
            "last_checkup_at": last_checkup_at,
        })
        if not updated:
            console.print("not found", style="yellow")
            raise SystemExit(1)
        console.print({k: updated[k] for k in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]})
    except Exception as e:
        console.print(f"error: {e}", style="bold red")
        raise SystemExit(1)


@cli.command("delete", help="delete a monkey by id")
@click.argument("monkey_id")
@click.pass_context
def delete_cmd(ctx: click.Context, monkey_id: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    ok = reg.delete(monkey_id)
    console.print("deleted" if ok else "not found")
    if not ok:
        raise SystemExit(1)


@cli.command("list", help="list monkeys (optional filters)")
@click.option("--name", default=None)
@click.option("--species", default=None)
@click.pass_context
def list_cmd(ctx: click.Context, name: Optional[str], species: Optional[str]):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    rows = reg.list({"name": name, "species": species})
    table = Table(title="monkeys")
    for col in ["monkey_id", "name", "species", "age_years", "favourite_fruit"]:
        table.add_column(col)
    for r in rows:
        table.add_row(r.get("monkey_id",""), r.get("name",""), str(r.get("species","")), str(r.get("age_years","")), r.get("favourite_fruit",""))
    console.print(table)


@cli.command("search", help="search by name or species")
@click.argument("query")
@click.pass_context
def search_cmd(ctx: click.Context, query: str):
    reg: MonkeyRegistryService = ctx.obj["registry"]
    rows = reg.search(query)
    console.print(f"found {len(rows)} result(s)")
    for r in rows:
        console.print({k: r[k] for k in ["monkey_id", "name", "species", "age_years"]})
```

---

## sanity checks – switch to ddb (no code beyond above)

> do these **from your project root**.

### 0) set aws env (use your provided assessment creds; do not commit)

```bash
export AWS_ACCESS_KEY_ID="<YOUR_KEY_ID>"
export AWS_SECRET_ACCESS_KEY="<YOUR_SECRET>"
export AWS_REGION="eu-west-1"
export DDB_TABLE="assessment-users"
```

### 1) quick table check

```bash
python - <<'PY'
import boto3
import os
r = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION','eu-west-1'))
print(r.describe_table(TableName=os.getenv('DDB_TABLE','assessment-users'))['Table']['TableStatus'])
PY
```

**expect:** `ACTIVE`.

### 2) create (ddb backend)

```bash
export PYTHONPATH=src
python -m monkey_registry.app create --backend ddb --name luna --species howler --age 4 --fruit figs
```

**expect:** prints a dict with a new `monkey_id` and `species: howler`.

### 3) list (ddb backend)

```bash
python -m monkey_registry.app list --backend ddb
```

**expect:** table including the new howler.

### 4) duplicate check still enforced

```bash
python -m monkey_registry.app create --backend ddb --name luna --species howler --age 5 --fruit banana ; echo $?
```

**expect:** red `error: duplicate name within species is not allowed` and `1`.

### 5) search works

```bash
python -m monkey_registry.app search --backend ddb luna
```

**expect:** `found N result(s)` ≥ 1, with at least the howler entry.

### 6) back to json (no aws)

```bash
python -m monkey_registry.app list --backend json
```

**expect:** your local json monkeys table (separate from ddb).

---

if all checks pass, your app is now switchable between json and dynamodb, with uniqueness and age rules enforced, ready to push. if anything fails, paste the exact command + full output and we’ll fix it step-by-step.

