# Datastore simulation: instructions for AI agents

Read this before you change anything in this folder. The human guide, with the build commands and
the expected result, is [README.md](README.md); running it is [HOW_TO_RUN.md](HOW_TO_RUN.md).

## What this example is

A primary key and a foreign key in Data Fabric, one-to-many: `DatastoreSimCustomer` (1) ← many
`DatastoreSimOrder`. Each entity's primary key is the `Id` Data Fabric assigns; `CustomerCode` and
`OrderNumber` are unique business keys; `DatastoreSimOrder.Customer` is a required `RELATIONSHIP`
field holding the customer row's `Id`. One Flow, `DatastoreSimFlow`, runs three nodes of one
function, `DatastoreSimFunction`, with `operation` fixed per node: `add_customers`, `add_orders`
(looks up the customers' `Id`s in one `in` query and refuses unknown customers), and
`orders_per_customer` (a LEFT JOIN in Python). The Evelyn piece it mirrors is `alert_analytics` →
`hit_analytics`, which Evelyn links by a shared text column with no foreign key.

## Source vs generated

| Edit these | Never edit these (regenerate instead) |
|---|---|
| `DatastoreSim/DatastoreSimFunction/{keys.py, main.py, test_main.py}` | `entry-points.json`, `main.mermaid`, `project.uiproj`, `.agent/`, `.claude/`, `.uipath/`, `uv.lock` (run `uv run uipath init` / `uv lock`) |
| `DatastoreSim/DatastoreSimFlow/DatastoreSimFlow.flow`, **only by re-running the README's commands** | `DatastoreSim.uipx`, `resources/` (managed by `uip solution …`) |
| `entities/*.create.json`, `data/*.json`, README, HOW_TO_RUN | `operate.json`, any `.bpmn`, `DatastoreSim/AGENTS.md` and `CLAUDE.md` and those inside the function: CLI boilerplate |

## Rules

1. **Nothing on the tenant without the user's go-ahead.** That covers `uip df entities create`,
   any `uip df records …` write, `uip maestro flow debug` and `uip solution publish` / `deploy`.
   Read-only calls (`validate`, `registry`, `resources refresh`, `resources list`) are fine.
2. **Never run `uipath auth`** in the function folder. It writes a token into `.env`, and
   `uip solution pack` ships `.env`. Use `uip login`.
3. **The foreign key holds the parent's `Id`, never a code or a name.** Keep the lookup in
   `add_orders` and the refusal of unknown customers in `keys.resolve_orders`; Data Fabric may not
   check that the parent exists (an open question in HOW_TO_RUN).
4. **Keep the data's traps.** C004 has no orders and O1005 names a customer that doesn't exist;
   `test_the_data_has_a_customer_with_no_orders_and_an_order_with_no_customer` guards both. If you
   change the data, change `EXPECTED` in the tests, the README's tables and HOW_TO_RUN together.
5. **The code and `entities/*.create.json` name the same fields.**
   `test_the_code_writes_exactly_the_entity_files_fields` enforces it. Field names are letters and
   digits only.
6. **The `.flow` is built by commands.** If you change it, change the README's commands, rebuild in
   an empty folder, and commit what the commands produce. The only hand edit is the End outputs
   (8f), shown with a `jq` command.
7. **Names are tenant-wide.** Don't reuse `DatastoreSimFunction`, `DatastoreSimFlow`,
   `DatastoreSimCustomer` or `DatastoreSimOrder` in another simulation.
8. **Mock data only, and label guesses.** Placeholder names only. Anything not verified locally or
   on a tenant is marked **Inference** or listed under "Things only the tenant run can confirm".

## Verify after any change

Run from `DatastoreSim/`:

| Check | Command | Expect |
|---|---|---|
| Tests | `cd DatastoreSimFunction && uv run pytest -q` | `18 passed` |
| Flow | `uip maestro flow validate DatastoreSimFlow/DatastoreSimFlow.flow` | `Valid`, no `Warnings` |
| Solution | `uip solution pack . --dry-run` | `Valid` |
| README | every `bash` block of steps 1–9, as written, in an empty folder | Exit 0; the `.flow` equal to the committed one apart from IDs |
