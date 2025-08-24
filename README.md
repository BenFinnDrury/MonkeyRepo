# monkey registry app

a fast, minimal cli that lets you **create, read, update, delete, list, and search** monkeys. it supports two storage backends:

* **json** file (local, default) – quick and offline
* **aws dynamodb** (live) – same api, switchable at runtime

> this repo demonstrates problem decomposition, small abstractions, and ai-assisted development. comments in code are kept lowercase by design.

---

## table of contents

* [features](#features)
* [data model](#data-model)
* [validation rules](#validation-rules)
* [project layout](#project-layout)
* [prerequisites](#prerequisites)
* [setup (local)](#setup-local)
* [run the cli (local json backend)](#run-the-cli-local-json-backend)
* [aws/dynamodb setup](#awsdynamodb-setup)
* [run the cli (dynamodb backend)](#run-the-cli-dynamodb-backend)
* [import/export](#importexport)
* [tests](#tests)
* [optional: species gsi](#optional-species-gsi)
* [troubleshooting](#troubleshooting)
* [design notes](#design-notes)

---

## features

* **crud** via a clean cli (click + rich)
* **validation** enforced centrally (age bounds, species cap, no duplicate name within species)
* **storage abstraction**: start with json; swap to dynamodb without changing commands
* **search** by name or species
* **import/export** json ↔ backends
* **tests** (pytest) for validation, cli smoke; ddb tested with local logic (json) and live sanity via cli

---

## data model

```json
{
  "monkey_id": "monkey_ab12cd34",       // uuid-based short id
  "name": "luna",                       // string, 2-40 chars
  "species": "marmoset",                // one of: capuchin|macaque|marmoset|howler
  "age_years": 2,                        // integer 0..45; marmoset ≤ 22
  "favourite_fruit": "mango",           // string
  "last_checkup_at": "2025-08-24T12:00:00Z", // iso datetime, optional
  "created_at": "2025-08-24T12:34:56",  // iso
  "updated_at": "2025-08-24T12:34:56"   // iso
}
```

---

## validation rules

* name required; trimmed length **2–40**
* species must be one of **capuchin, macaque, marmoset, howler**
* age\_years must be integer **0–45**
* if species = **marmoset**, then **age\_years ≤ 22**
* **no duplicate name within the same species** (case-insensitive)

---

## project layout

```
├─ AI_logs              # screenshot & downloaded coding canvas evidence of prompts x3
├─ README.md
├─ process_log.md 
├─ requirements.txt
├─ pytest.ini
├─ .gitignore
├─ .env.example                # placeholders only; never commit real creds
├─ data/
│  └─ monkeys.json             # local json store (dev default)
├─ src/
│  └─ monkey_registry/
│     ├─ app.py                # entrypoint (cli shim)
│     ├─ cli.py                # click commands
│     ├─ models.py             # species enum, validation, (de)serialization
│     ├─ services/
│     │  └─ registry.py        # domain rules + persistence orchestration
│     └─ storage/
│        ├─ base.py            # storage interface
│        ├─ json_store.py      # local json backend
│        └─ dynamodb_store.py  # dynamodb backend (pk/sk = MONKEY#{id})
└─ tests/
   ├─ test_validation.py
   └─ test_cli_smoke.py
```

---

## prerequisites

* python **3.9–3.12**
* pip, venv
* (for ddb) aws credentials with access to the table

---

## setup (local)

```bash
# clone
git clone <REPO_URL>
cd <REPO_FOLDER>

# venv
python -m venv .venv
source .venv/bin/activate   # windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# ensure python sees src
export PYTHONPATH=src

# optional: initialize local json store
mkdir -p data && printf "[]\n" > data/monkeys.json
```

### quick smoke (local json)

```bash
python -m monkey_registry.app --backend json list
```

expected: a table (possibly empty).

---

## run the cli (local json backend)

> group option must come **before** the subcommand in click.

```bash
export PYTHONPATH=src

# create
python -m monkey_registry.app --backend json create --name luna --species marmoset --age 2 --fruit mango

# list
python -m monkey_registry.app --backend json list

# search (name or species)
python -m monkey_registry.app --backend json search marmoset

# update (change fruit)
python -m monkey_registry.app --backend json update <monkey_id> --fruit pineapple

# delete
python -m monkey_registry.app --backend json delete <monkey_id>
```

**duplicate rule check**

```bash
python -m monkey_registry.app --backend json create --name luna --species marmoset --age 3 --fruit banana ; echo $?
# expect: error + exit code 1
```

---

## aws/dynamodb setup

> do not commit real credentials. use environment variables.

```bash
export AWS_ACCESS_KEY_ID="<YOUR_KEY_ID>"
export AWS_SECRET_ACCESS_KEY="<YOUR_SECRET>"
export AWS_REGION="eu-west-1"
export DDB_TABLE="assessment-users"
```

**sanity: table reachable**

```bash
python - <<'PY'
import os,boto3
c=boto3.client('dynamodb', region_name=os.getenv('AWS_REGION','eu-west-1'))
print(c.describe_table(TableName=os.getenv('DDB_TABLE','assessment-users'))['Table']['TableStatus'])
PY
# expect: ACTIVE
```

**about the table**

* partition key (**PK**): string
* sort key (**SK**): string
* items for monkeys have `PK = SK = "MONKEY#{monkey_id}"` and attribute `entity="MONKEY"`
* helper attributes `name_lc`, `species_lc` are stored for filtering

---

## run the cli (dynamodb backend)

```bash
export PYTHONPATH=src

# create
python -m monkey_registry.app --backend ddb create --name alex --species howler --age 4 --fruit figs

# list / search
python -m monkey_registry.app --backend ddb list
python -m monkey_registry.app --backend ddb search alex

# duplicate rule
python -m monkey_registry.app --backend ddb create --name alex --species howler --age 5 --fruit banana ; echo $?
# expect: error + exit code 1

# update / delete
MID_DDB=$(python -m monkey_registry.app --backend ddb list | sed 's/│/|/g' | sed -n 's/.*\(monkey_[a-z0-9]\{8\}\).*/\1/p' | head -n1)
python -m monkey_registry.app --backend ddb update "$MID_DDB" --fruit dates
python -m monkey_registry.app --backend ddb delete "$MID_DDB"
```

---

## import/export

**import (upload a json array into a backend)**

```bash
# validate only (no writes)
python -m monkey_registry.app --backend ddb import-json --file data/monkeys.json --dry-run

# insert-only
python -m monkey_registry.app --backend ddb import-json --file data/monkeys.json --mode create

# upsert (create or update if name+species already exists)
python -m monkey_registry.app --backend ddb import-json --file data/monkeys.json --mode upsert
```

**export (dump backend to json)**

```bash
# export all records from ddb to a file (handles Decimal → int/float)
python -m monkey_registry.app --backend ddb export-json --file export/ddb-all.json --force

# filter by species
python -m monkey_registry.app --backend ddb export-json --species marmoset --file export/ddb-marmoset.json --force
```

---

## tests

```bash
# run all tests
python -m pytest -q

# or target a file
python -m pytest -q tests/test_validation.py
```

* `test_validation.py`: model validation (age caps, species, name length)
* `test_cli_smoke.py`: creates/duplicates/searches via the cli in an isolated temp json db

> note: ddb integration is validated via the live cli sanity above. (stubbing low-level attributevalue shapes adds noise for this scope.)

---

## optional: species gsi

**why**: speed up `list --species` and `search <species>` on dynamodb.

**index**: `GSI_Species` with partition key `species_lc` (S) and sort key `name_lc` (S), projection `ALL`.

**create via console**

1. dynamodb → tables → assessment-users → indexes → create index
2. partition key: `species_lc` (string); sort key: `name_lc` (string); projection: **all**
3. wait until status = **active**

> if you cannot alter the table (limited permissions), the app transparently falls back to scans and still works.

---

## troubleshooting

* **no such option: --backend** → put `--backend` **before** the subcommand (click rule), e.g. `python -m monkey_registry.app --backend ddb list`.
* **module not found: monkey\_registry** → `export PYTHONPATH=src` in your terminal, or run via pycharm with `src` as sources root.
* **unable to locate credentials** → export `AWS_*` env vars in the same terminal tab.
* **resource not found** → confirm `DDB_TABLE=assessment-users` and `AWS_REGION=eu-west-1`.
* **decimal not json serializable** during export → the export command already converts `Decimal` to `int/float`. update `cli.py` if you pulled an older version.

---

## design notes

* **storage interface** keeps the cli/service independent of the backend.
* **service layer** centralizes domain rules (so json and ddb behave identically).
* **cli** provides consistent commands; backend is selected per-invocation.
* **tests** target core rules and cli behavior; live ddb is exercised via explicit sanity commands.

---

## license

mit
