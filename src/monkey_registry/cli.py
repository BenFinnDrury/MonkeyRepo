from __future__ import annotations
import json
from .models import Monkey


import os
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .services.registry import MonkeyRegistryService
from .storage import JsonStorage
from .storage.dynamodb_store import DynamoStorage
from decimal import Decimal

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

@cli.command("import-json", help="import monkeys from a json array file into the selected backend")
@click.option("--file", "file_path", default="data/monkeys.json", show_default=True, help="path to source json file")
@click.option("--mode", type=click.Choice(["create", "upsert"], case_sensitive=False), default="create", show_default=True, help="create = insert only; upsert = create or update")
@click.option("--dry-run", is_flag=True, help="validate only, no writes")
@click.pass_context
def import_json_cmd(ctx: click.Context, file_path: str, mode: str, dry_run: bool):
    # all comments in lowercase
    reg: MonkeyRegistryService = ctx.obj["registry"]
    backend = ctx.obj.get("backend", "json")

    # load file
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"error reading {file_path}: {e}", style="bold red")
        raise SystemExit(1)

    if not isinstance(data, list):
        console.print("error: json must be an array of objects", style="bold red")
        raise SystemExit(1)

    created = 0
    updated = 0
    skipped = 0
    failed = 0

    for row in data:
        try:
            # validate and normalize
            _ = Monkey.from_dict(row)

            if dry_run:
                created += 1
                continue

            if mode == "upsert":
                try:
                    reg.create(row)
                    created += 1
                    continue
                except Exception as e:
                    if "duplicate name" in str(e).lower():
                        # find existing by filters; update it
                        matches = reg.list({"name": row.get("name"), "species": row.get("species")})
                        if matches:
                            mid = matches[0]["monkey_id"]
                            reg.update(mid, row)
                            updated += 1
                            continue
                        else:
                            skipped += 1
                            continue
                    else:
                        raise
            else:
                reg.create(row)
                created += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                skipped += 1
            else:
                failed += 1
            console.print(f"skip: {e} for row name={row.get('name')} species={row.get('species')}", style="yellow")

    console.print(f"done on backend={backend}. created={created}, updated={updated}, skipped={skipped}, failed={failed}, total={len(data)}")

@cli.command("export-json", help="export monkeys to a json array file from the selected backend")
@click.option("--file", "file_path", default="export/monkeys-export.json", show_default=True, help="output path for json file")
@click.option("--species", default=None, help="optional species filter")
@click.option("--name", default=None, help="optional name filter (substring, case-insensitive)")
@click.option("--pretty/--compact", default=True, show_default=True, help="pretty print json with indent=2")
@click.option("--force", is_flag=True, help="overwrite the output file if it already exists")
@click.pass_context
def export_json_cmd(ctx: click.Context, file_path: str, species: str | None, name: str | None, pretty: bool, force: bool):
    # all comments in lowercase
    from pathlib import Path

    reg: MonkeyRegistryService = ctx.obj["registry"]
    backend = ctx.obj.get("backend", "json")

    # gather rows via filters (works for both json and ddb backends)
    rows = reg.list({"name": name, "species": species})

    # convert decimal values (from dynamodb) into json-safe numbers
    def _json_safe(x):
        if isinstance(x, list):
            return [_json_safe(i) for i in x]
        if isinstance(x, dict):
            return {k: _json_safe(v) for k, v in x.items()}
        if isinstance(x, Decimal):
            # use int when value is whole, else float
            return int(x) if x == x.to_integral_value() else float(x)
        return x

    rows = _json_safe(rows)

    # prepare filesystem
    out = Path(file_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        console.print(f"error: {file_path} already exists. use --force to overwrite.", style="bold red")
        raise SystemExit(1)

    # sort for stable output (species, then name)
    rows_sorted = sorted(rows, key=lambda r: (str(r.get("species","")), str(r.get("name",""))))

    # write
    try:
        with out.open("w", encoding="utf-8") as f:
            json.dump(rows_sorted, f, ensure_ascii=False, indent=(2 if pretty else None))
        console.print(f"exported {len(rows_sorted)} record(s) to {file_path} from backend={backend}")
    except Exception as e:
        console.print(f"error writing {file_path}: {e}", style="bold red")
        raise SystemExit(1)
