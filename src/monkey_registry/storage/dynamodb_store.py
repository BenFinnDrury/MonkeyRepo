from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key



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
        # prefer gsi query when species present; else scan
        if filters and (filters.get("species") or "").strip():
            species = (filters.get("species") or "").strip().lower()
            name = (filters.get("name") or "").strip().lower()
            try:
                if name:
                    res = self.table.query(
                        IndexName="GSI_Species",
                        KeyConditionExpression=Key("species_lc").eq(species) & Key("name_lc").begins_with(name),
                    )
                else:
                    res = self.table.query(
                        IndexName="GSI_Species",
                        KeyConditionExpression=Key("species_lc").eq(species),
                    )
                items = res.get("Items", [])
                return [self._from_item(it) for it in items]
            except Exception:
                # fallback to scan if index missing or query fails
                pass
        fe = Attr("entity").eq("MONKEY")
        if filters:
            name = (filters.get("name") or "").strip().lower()
            species = (filters.get("species") or "").strip().lower()
            if species:
                fe = fe & Attr("species_lc").eq(species)
            if name:
                fe = fe & Attr("name_lc").contains(name)
        res = self.table.scan(FilterExpression=fe)
        return [self._from_item(it) for it in res.get("Items", [])]

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return []
        # try species-only query first via gsi
        try:
            res = self.table.query(
                IndexName="GSI_Species",
                KeyConditionExpression=Key("species_lc").eq(q),
            )
            items = res.get("Items", [])
            if items:
                return [self._from_item(it) for it in items]
        except Exception:
            pass
        # fallback: scan contains on name or species
        fe = (Attr("entity").eq("MONKEY")) & (Attr("name_lc").contains(q) | Attr("species_lc").contains(q))
        res = self.table.scan(FilterExpression=fe)
        return [self._from_item(it) for it in res.get("Items", [])]

    def find_by_name_species(self, name: str, species: str) -> Optional[Dict[str, Any]]:
        n = (name or "").strip().lower()
        s = (species or "").strip().lower()
        try:
            res = self.table.query(
                IndexName="GSI_Species",
                KeyConditionExpression=Key("species_lc").eq(s) & Key("name_lc").eq(n),
                Limit=1,
            )
            items = res.get("Items", [])
            return self._from_item(items[0]) if items else None
        except Exception:
            fe = Attr("entity").eq("MONKEY") & Attr("species_lc").eq(s) & Attr("name_lc").eq(n)
            res = self.table.scan(FilterExpression=fe)
            items = res.get("Items", [])
            return self._from_item(items[0]) if items else None