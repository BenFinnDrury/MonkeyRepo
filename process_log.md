# process log 

**candidate:** Ben Drury
**date:** 2025-08-24 (Europe/Dublin)
**goal:** ship a basic CRUD "Monkey Registry" with json + dynamodb backends, validation, one test, and clear docs, using AI effectively.

---

## 1) timeline (rough estimates given after known 4:30 start)

* **16:30–17:10** — *project bootstrap*

  * read spec; created local venv and skeleton structure (`src/`, `tests/`, `data/`).
  * sanity verified interpreter + `PYTHONPATH=src`.

* **17:10–17:25** — *model & validation*

  * implemented `models.py` with `Species` enum, `Monkey` dataclass, validation (name length, species, age bounds, marmoset ≤ 22), iso parsing.
  * smoke-tested object creation + validation exceptions.

* **17:25–17:40** — *storage abstraction + json backend*

  * defined `BaseStorage` protocol.
  * implemented `JsonStorage` (read/write `data/monkeys.json`).
  * sanity: create/get/list/search in json file.

* **17:40–18:05** — *service + cli*

  * added `MonkeyRegistryService` enforcing *no duplicate name within a species*.
  * built `click` + `rich` CLI (`create/get/update/delete/list/search`).
  * fixed import mode to support `python -m monkey_registry.app`.

* **18:05–18:15** — *bugfix: uniqueness enum value*

  * issue: duplicates slipped because `str(enum)` returned `Species.X`.
  * fix: compare using `.value`.
  * sanity: duplicate create now fails with exit code `1`.

* **18:15–18:30** — *tests*

  * `tests/test_validation.py` (age cap + happy path) and `tests/test_cli_smoke.py` (isolated temp json).
  * ran `pytest -q` → green.

* **18:30–18:55** — *dynamodb backend*

  * added `DynamoStorage` (PK=SK=`MONKEY#{id}`; helper fields `name_lc`, `species_lc`).
  * wired backend switch (`--backend json|ddb` or `BACKEND=ddb`).
  * creds troubleshooting: exported `AWS_*`, verified `describe-table` → ACTIVE.

* **18:55–19:05** — *ddb sanity + table parsing pitfalls*

  * confirmed create/list/search on ddb; fixed common Click usage (`--backend` before subcommand).
  * improved id capture for delete (don’t rely on rich table; use `search` or create output).

* **19:05–19:15** — *import/export*

  * `import-json` (create|upsert, optional `--dry-run`) routing via service for consistent rules.
  * `export-json` with Decimal → int/float conversion for ddb results.

* **19:15–19:40** — *docs tidy + finalize report*

  * finalized process log and prompts; proof-read README.
  * ran full sanity on both backends (json + ddb): create/list/search/update/delete, duplicate rule, age cap.

* **19:40–20:00** — *clone + push + submit (roughly, not complete as of submission)*

  * cloned assessment repo to a fresh folder; copied project files (excluding `.venv`, caches, and `.env`).
  * installed deps, `pytest -q` green, quick CLI smoke (json + ddb), committed and pushed to `main`.
  * submitted the GitHub repo link.

> finish: **~20:00** 

## 2) initial feature spec (fed to ai)

> **spec:** build a minimal monkey registry cli with:
>
> * model: `monkey_id`, `name` (2–40), `species` enum (capuchin|macaque|marmoset|howler), `age_years` (0–45, marmoset ≤22), `favourite_fruit`, `last_checkup_at` (iso optional), timestamps.
> * storage: start with json file; ensure system is easy to swap to dynamodb.
> * service: enforce *no duplicate name within species* (case-insensitive).
> * cli: create/read/update/delete/list/search.
> * tests: at least one (validation + a cli smoke).
> * stretch: import/export json; optional ddb gsi for species.
>
> Ensure the process of making this app is step by step, handle one file at a time. I have never engaged with AWS integration, so please return detailed explanations at each step. Give plenty of sanity checks. 
> 
> If further clarification is necessary on any of the specifications, do not proceed, request clarification and proceed once permitted. If multiple solutions match my prompt, return options with pros and cons for each; awaait follow up. 
> 
> First return a plan for the project with file structure, once approved, await your first task.
---

## 3) ai tooling used

* **assistant:** chatgpt - 5 Thinking (prompt-driven codegen + iterative fixes).
* **scope of use:** skeletons (model/storage/service/cli), test scaffolding, bug triage (enum `.value`), ergonomics (click usage), ddb decimals fix, import/export flows, docs, sanity checks. 

### key prompts (exact snippets)

1. **bootstrap (after spec):**

   > "generate a dataclass model for a monkey with species enum and validation (name 2–40, age 0–45 with marmoset ≤22), plus `to_dict`/`from_dict`; keep comments lowercase."

2. **storage + service:**

   > "create a json storage class and a service that enforces no duplicate name within species; provide simple list/search filters and a `find_by_name_species` helper."

3. **cli + click:**

   > "write a click cli with commands create/get/update/delete/list/search using the service."

4. **bugfix (duplicates):**

   > "i still can create duplicate name within species, investigate the service and fix."

5. **ddb backend:**

   > "add a dynamodb storage using pk=sk=MONKEY#{id}, store lowercase helper fields, and implement list/search via scan; keep interface identical to json."

6. **import/export & decimals:**

   > "add `import-json` (create/upsert) and `export-json`. convert boto3 decimal types to json-safe ints/floats."

7. **gsi :**

   > "add a GSI or species to support search, explain in detail after implementation"

---

## 4) trade-offs & reasoning

* **cli (python) over web ui**: fastest to ship under time; assessment allows cli.
* **json first, ddb second**: build locally, then swap backend. I was unfamiliar with AWS and wanted to ensure a working app before attempting integration. 
* **simple scans in ddb**: acceptable for tiny dataset; optional GSI documented for performance without breaking behavior.
* **per-item writes** (import): clearer error handling than batch for this scope.
* **tests minimal but meaningful**: validate domain rules + cli smoke; heavier ddb stubbing omitted to keep within time (live cli sanity used instead).

---

## 5) blockers & how they were unblocked

* **relative import error** (`attempted relative import`): switched to absolute import + `python -m` usage.
* **duplicate rule not firing**: used `.species.value` instead of `str(enum)`.
* **click option parsing** (`No such option: --backend`): group options must precede subcommand; documented and adjusted examples.
* **ddb credentials** (`Unable to locate credentials`): exported `AWS_*` in the same terminal tab; verified with `describe-table`.
* **json export failure** (`Decimal is not JSON serializable`): converted `Decimal → int/float` before writing.
* **id scraping from rich tables**: avoided parsing tables; used `search` output or captured id on create.

---

## 6) verification checklist (final)

* json backend: create/list/search/update/delete; duplicate rule returns code `1`; marmoset age cap enforced; tests pass.
* ddb backend: same behaviors; table reachable; import/export OK; optional GSI notes provided.
* README: setup/run (local + ddb), import/export, tests, troubleshooting.
* secrets: none committed; `.env.example` included.

---

## 7) next steps (if time remains)

* add `insights`: count by species, average age by species.
* unit tests for dynamodb using lightweight fakes or higher-level golden tests.
* optional small web ui (streamlit) reusing the same service.
