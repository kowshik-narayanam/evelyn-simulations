# Datastore simulation: a primary key and a foreign key in Data Fabric

**The point of this example:** two tables in a one-to-many relationship, the shape every relational
store has. One customer has zero or many orders; each order belongs to exactly one customer.

- **The primary key:** every customer row gets an `Id`, a GUID that Data Fabric assigns on insert.
  You never choose it. `CustomerCode` (`C001`…) is a second, human key: unique, but not the
  primary key.
- **The foreign key:** each order has a `Customer` field of type `RELATIONSHIP`. It holds the `Id`
  of the customer row it belongs to, and it is required, so no order exists without a customer.
- **Writing an order:** the caller knows the customer as `C001`, but the foreign key needs that
  customer's `Id`. So the code looks the codes up first, in one query (`CustomerCode IN (…)`), and
  refuses an order whose customer doesn't exist.
- **Reading it back:** every customer with their order count and total, a customer with no orders
  included. That is a `LEFT JOIN`, done in Python on `Customer = Id`.

```
DatastoreSimFlow
  Manual trigger ─► Add customers ──────────► Add orders ─────────────────────► Orders per customer ─► End
  customers,        insert 5 rows (1 batch);   look up the customers' Ids         read both tables,        customers_added,
  orders            Data Fabric assigns        (1 query, IN); refuse O1005        count and total per      orders_added,
                    each row's Id              (no customer C999); insert 7       customer, 0 for C004     orders_rejected, …,
                                               rows (1 batch)                                              summary

DatastoreSimCustomer (1) ◄──── Customer ──── (0..many) DatastoreSimOrder
Id            primary key, assigned            Id            primary key, assigned
CustomerCode  unique business key              OrderNumber   unique business key
CustomerName                                   Customer      foreign key → DatastoreSimCustomer.Id, required
                                               Amount        DECIMAL, 2 places
```

## Why: Evelyn's analytics tables

Evelyn's closest one-to-many pair is its analytics: one row per alert in `alert_analytics`, and
one row per hit in `hit_analytics`. An alert has zero hits (nothing matched) or many. Evelyn links
the two with no foreign key at all: both rows carry the same text column, `transaction_uuid`.

| Evelyn (`names-screening`) | Does | Here |
|---|---|---|
| `alert_analytics` (migration `034_1_alert_analytics_table.yaml`) | One row per alert | `DatastoreSimCustomer`: one row per customer |
| `hit_analytics` (`034_2_hit_analytics_table.yaml`) | One row per hit; an alert has zero or many | `DatastoreSimOrder`: zero or many per customer |
| `uuid NVARCHAR(36)`, `defaultValueComputed: NEWID()`, unique, not null (`034_1…:10-15`); `@Id @GeneratedValue` on the entity (`AlertAnalytics.java:23-26`) | The row's key, made by the database | `Id`, made by Data Fabric |
| `transaction_uuid NVARCHAR(36)` on both tables (`034_1…:17`, `034_2…:17`); no foreign key constraint and no JPA relationship anywhere in the migrations or entities | Links an alert's hits to it, by convention only | `Customer`, a `RELATIONSHIP` field: a declared foreign key that holds the parent row's `Id` |
| `initAlertAnalytics` saves an alert only if none exists for the transaction (`AnalyticsService.java:47-48`) | Keeps one alert per transaction, in code | `CustomerCode` and `OrderNumber` are `isUnique`: Data Fabric refuses a duplicate |
| `initHitsAnalytics` saves one hit per WLE, none when the list is empty (`AnalyticsService.java:61-63`) | Zero or many | C004 Alice Wonderland has no orders |
| `initFullAnalytics` is `@Transactional` (`AnalyticsService.java:80-81`) | Alert and hits commit together | Two separate writes. Data Fabric has no transaction across two entities |
| Joins written as JPQL on the text column: `Transaction t JOIN QcReportData q ON t.uuid = q.transactionId` (`TransactionRepository.java:86`) | Reads the two tables together | `keys.summarize`: both entities read, joined on `Customer = Id` |

Evelyn paths are under `names-screening-package/src/main/resources/datastore/migrations/`,
`names-screening-core/` and `names-screening-jnw/`. Line numbers are from `names-screening`
`master` @ `6dcf7f9d3` (2026-09-24). The model repo `nss-classification-model` isn't used here.

## WorkFusion → UiPath

| WorkFusion (Evelyn on MSSQL) | Here (Data Fabric) |
|---|---|
| A table, created by a Liquibase changeset | An **entity**, created by `uip df entities create --file entities/<Name>.create.json` |
| A primary key column, `NEWID()` | `Id`: every entity has it, assigned on insert, never set by you |
| A unique constraint | `isUnique` on one field |
| A foreign key column (Evelyn uses none) | A `RELATIONSHIP` field. Its value is always the parent's `Id`; a code or a name is refused |
| `INSERT` with a subquery for the parent's key | Look the parent's `Id` up first (`retrieve_records` with an `in` filter), then insert |
| `SELECT … FROM order WHERE customer_id = ?` | `retrieve_records` (or `uip df records query`) with a filter on `Customer` = the customer's `Id` |
| `LEFT JOIN … GROUP BY` | Read both entities, count in Python. A server-side group-by would drop the customers with no orders |
| `@Transactional` across two tables | Nothing spans two entities. A customer row stays even if its orders fail |
| A bot step | A function node: `DatastoreSimFunction`, with `operation` fixed per node |
| A BP | The Maestro Flow `DatastoreSimFlow` |

**Status (2026-10-16):**
- **Verified locally:**
  - the build commands below, re-run as written in an empty folder;
  - 18 tests pass;
  - eight deliberate mistakes each fail the tests: an INNER JOIN that drops C004, the customer code
    stored in the foreign key instead of the `Id`, no foreign key check, a total that keeps only
    the last amount, errors raised instead of reported, `null` orders from the Flow refused, only the
    first page read, a relationship read back as an object and not unwrapped;
  - the Flow `validate`s as Valid with no warnings;
  - `solution pack` is Valid.
- **Not run yet:** the tenant run. Nothing in this folder has been created, uploaded or run on a
  tenant. Whether Data Fabric itself refuses an order whose `Customer` points at no customer, and
  what deleting a customer does to its orders, are [open questions](HOW_TO_RUN.md#things-only-the-tenant-run-can-confirm).

## Build it yourself

Every command below, in order, builds this example from an empty folder. The code files are copied
from this folder; type them yourself if you prefer.

- **Start here:** open a terminal in this folder, the one with this README. Step 1 remembers it as
  `$EXAMPLE`.
- **Where:** the commands build in `~/rebuild/datastore-simulation`. Change the path in step 1 if
  you like; everything after it is relative.
- **One terminal:** run every block in the same terminal, top to bottom. `$EXAMPLE` (step 1) and
  the function's node type (step 8) live in shell variables, and a new terminal forgets them.
- **Local only:** nothing in steps 1–9 changes the tenant. `uip maestro flow validate`, `registry`,
  `uip solution resources refresh` and `pack` read from the tenant you're logged into, read only.
  The entities are created on the tenant in [HOW_TO_RUN.md](HOW_TO_RUN.md#3-on-the-tenant).
- **Different IDs:** your Solution, project and function get new IDs. Your `.flow` matches this
  folder's except for those keys.
- **Needs:** `uv`, the `uip` CLI (logged in: `uip login status`) and `jq`.

| Build step | Section |
|---|---|
| The folder, the data and the two entity designs | [1](#1-the-folder-the-data-and-the-entity-designs) |
| The Solution and the function project | [2](#2-the-solution)–[3](#3-the-function-project) |
| The code and the tests | [4](#4-the-code)–[5](#5-tests) |
| The schema and a local run | [6](#6-the-schema-and-a-local-run) |
| Register the function, then the Flow | [7](#7-register-the-function)–[8](#8-the-flow-datastoresimflow) |
| `resources refresh`, then pack | [9](#9-resources-and-pack) |

### 1. The folder, the data and the entity designs

```bash
EXAMPLE=$(pwd)
```

```bash
mkdir -p ~/rebuild/datastore-simulation/data ~/rebuild/datastore-simulation/entities
```

```bash
cd ~/rebuild/datastore-simulation
```

```bash
cp "$EXAMPLE"/data/*.json data/
```

```bash
cp "$EXAMPLE"/entities/*.create.json entities/
```

**The data.** Five customers and eight orders, built so a wrong join or a missing check shows:

| Customer | Name | Orders | Total | Why it's there |
|---|---|---|---|---|
| C001 | Gill Bates | O1001, O1003, O1007 | 200.50 | Many orders, spread through the file |
| C002 | Melon Eusk | O1004 | 300.00 | One order |
| C003 | Beff Jezos | O1002, O1006 | 57.10 | |
| C004 | Alice Wonderland | none | 0.00 | **Zero orders:** an INNER JOIN would drop her |
| C005 | John Doe | O1008 | 5.25 | |
| C999 | (no such customer) | O1005 | | **An order with no customer:** the foreign key check refuses it |

**The two entity designs**, as `uip df entities create --file` takes them:

| Entity | Field | Type | Options | Role |
|---|---|---|---|---|
| `DatastoreSimCustomer` | `Id` | GUID | assigned | **Primary key** (every entity has it; not in the file) |
| | `CustomerCode` | `STRING` 10 | required, unique | Business key |
| | `CustomerName` | `STRING` 100 | required | |
| `DatastoreSimOrder` | `Id` | GUID | assigned | Primary key |
| | `OrderNumber` | `STRING` 20 | required, unique | Business key |
| | `Customer` | `RELATIONSHIP` → `DatastoreSimCustomer`, displays `CustomerCode` | required | **Foreign key** |
| | `Amount` | `DECIMAL`, 2 places, 0–1,000,000 | required | |

The relationship's two IDs, which entity it points at and which field it displays, exist only once
the customer entity has been created, so `jq` adds them on the tenant
([HOW_TO_RUN.md](HOW_TO_RUN.md#3-on-the-tenant), step 3).

**Check:** `jq length data/customers.json data/orders.json` prints `5` and `8`.

### 2. The Solution

```bash
uip solution init DatastoreSim
```

**Check:** `ls DatastoreSim` shows `AGENTS.md`, `CLAUDE.md` and `DatastoreSim.uipx`.

### 3. The function project

```bash
cd DatastoreSim
```

```bash
mkdir DatastoreSimFunction
```

```bash
cd DatastoreSimFunction
```

```bash
uv init --bare --python 3.11
```

```bash
uv python pin 3.11
```

```bash
uv add "uipath==2.14.27"
```

```bash
uv run uipath new DatastoreSimFunction --type function
```

```bash
uv add --dev pytest
```

```bash
uv add "pydantic>=2.10,<3"
```

`uipath new` rewrites `pyproject.toml`, which is why pytest is added after it.

**Check:** `ls -a` shows `.python-version`, `.venv`, `main.py`, `pyproject.toml`, `uipath.json`,
`uv.lock`.

### 4. The code

```bash
cp "$EXAMPLE"/DatastoreSim/DatastoreSimFunction/{main.py,keys.py,test_main.py} .
```

| File | Holds |
|---|---|
| `keys.py` | **The lesson, with no SDK.** `Customer`, `Order`, `CustomerSummary`; `resolve_orders` turns each order's customer code into that customer's `Id` and refuses unknown customers; `summarize` joins orders to customers on `Customer = Id`, every customer included |
| `main.py` | The three operations, one per Flow node, and every Data Fabric call |
| `test_main.py` | 18 tests, with a fake Data Fabric that enforces both unique keys and refuses an order whose `Customer` isn't a customer's `Id` |

| Operation | Data Fabric calls | Does |
|---|---|---|
| `add_customers` | name → entity `Id`; one `insert_records` batch | Writes one row per customer. Returns `customer_ids`: each code with the `Id` Data Fabric gave it |
| `add_orders` | the two entity `Id`s; one `retrieve_records` with `CustomerCode IN (C001, …)`; one `insert_records` batch | Looks the customers up, refuses O1005, writes the other seven with `Customer` = the customer's `Id` |
| `orders_per_customer` | the two entity `Id`s; every row of each, page by page | Counts and totals each customer's orders, 0 for C004 |

Two kinds of refusal come back separately: `orders_rejected` is our foreign key check (no such
customer), and `customers_failed` / `orders_failed` are Data Fabric's (a unique key already
taken). Neither stops the run; Data Fabric errors set `ok` to `false`.

**Check:** `grep -c "def _op_" main.py` prints `3`.

### 5. Tests

```bash
uv run pytest -q
```

**Check:** `18 passed`.

| Test | Shows |
|---|---|
| `test_an_order_stores_its_customers_id_not_the_code` | The foreign key holds the parent's `Id` |
| `test_an_order_for_an_unknown_customer_is_rejected_before_data_fabric_sees_it` | Our check, O1005 |
| `test_the_customer_lookup_is_one_query_with_in` | One query for all five codes, not one per order |
| `test_every_customer_is_listed_including_one_with_no_orders` | The LEFT JOIN: C004 with 0 |
| `test_a_second_c001_is_refused_by_the_unique_business_key` | `isUnique` |
| `test_running_the_flow_twice_adds_nothing_the_second_time` | Both unique keys at once: 0 added, 5 + 7 refused, the summary unchanged |
| `test_a_relationship_read_back_as_the_parent_row_still_joins` | Works whichever shape a read returns |

### 6. The schema and a local run

```bash
uv run uipath init
```

**Check:** `entry-points.json` exists; `bindings.json` holds `"resources": []`. The entities aren't
bindings: the code finds them by name.

**A local run, with no tenant.** `keys.py` runs on its own, with made-up `Id`s standing in for the
ones Data Fabric assigns:

```bash
uv run python keys.py ../../data/customers.json ../../data/orders.json > /tmp/datastore-local.json
```

```bash
jq -c '.rejected, (.summary[] | [.customer_code, .order_count, .total_amount]), .order_rows[0]' /tmp/datastore-local.json
```

**Check:** `["O1005: no customer C999"]`, then one line per customer, C004 with `0`, then
`{"OrderNumber":"O1001","Customer":"id-of-C001","Amount":120.5}`: the order holds its customer's
`Id`, not `C001`.

### 7. Register the function

```bash
cd ..
```

```bash
uip solution projects add ./DatastoreSimFunction
```

```bash
find resources -type f
```

**Check:** two files, the function's package and process. Nothing for the entities: the Solution
doesn't create them, so they must exist on the tenant before the first run.

### 8. The Flow: DatastoreSimFlow

**8a. Create the Flow project.** From `DatastoreSim/` (you're there):

```bash
uip maestro flow init DatastoreSimFlow
```

**Check:** the output shows `"Status": "Registered"`.

```bash
cd DatastoreSimFlow
```

**8b. Keep the function's node type in a shell variable.**

```bash
FN=$(uip maestro flow registry search DatastoreSimFunction --local --output plain --output-filter "[?DisplayName=='DatastoreSimFunction' && Category=='function'].NodeType | [0]")
```

```bash
echo "$FN"
```

**Check:** it prints `uipath.core.function.…`.

**8c. The nodes.** Three function nodes with a fixed `operation`, then the End. A node's ID comes
from its label: `Orders per customer` becomes `ordersPerCustomer1`.

```bash
uip maestro flow node add DatastoreSimFlow.flow "$FN" --label "Add customers" --input '{"operation": "add_customers", "customers": "=js:$vars.start.output.customers"}'
```

```bash
uip maestro flow node add DatastoreSimFlow.flow "$FN" --label "Add orders" --input '{"operation": "add_orders", "orders": "=js:$vars.start.output.orders"}'
```

```bash
uip maestro flow node add DatastoreSimFlow.flow "$FN" --label "Orders per customer" --input '{"operation": "orders_per_customer"}'
```

```bash
uip maestro flow node add DatastoreSimFlow.flow core.control.end --label "End"
```

```bash
jq -c '.nodes[] | {id, inputs: (.inputs | del(.entryPointId))}' DatastoreSimFlow.flow
```

**Check:** five nodes. Each function node lists the input it was given and `null` for the list it
wasn't, which `main.py` turns into `[]`.

| Node ID | Operation | Inputs | Why this order |
|---|---|---|---|
| `addCustomers1` | `add_customers` | `customers` ← the trigger | Parents first: an order needs its customer's `Id` |
| `addOrders1` | `add_orders` | `orders` ← the trigger | Looks the customers up itself, as a later run with new orders would |
| `ordersPerCustomer1` | `orders_per_customer` | none | Reads back what the two nodes wrote |

**8d. The Flow's inputs and outputs.**

```bash
uip maestro flow variable add DatastoreSimFlow.flow customers --direction in --type array --sub-type object --default-value '[]' --description "Customers to add: customer_code, customer_name"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow orders --direction in --type array --sub-type object --default-value '[]' --description "Orders to add: order_number, customer_code, amount"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow customers_added --direction out --type number --description "Customer rows written by this run"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow customers_failed --direction out --type array --sub-type string --description "Customers Data Fabric refused, e.g. a CustomerCode already there"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow orders_added --direction out --type number --description "Order rows written by this run"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow orders_rejected --direction out --type array --sub-type string --description "Orders refused by the foreign key check: no such customer"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow orders_failed --direction out --type array --sub-type string --description "Orders Data Fabric refused, e.g. an OrderNumber already there"
```

```bash
uip maestro flow variable add DatastoreSimFlow.flow summary --direction out --type array --sub-type object --description "Every customer with order_count and total_amount, those with no orders included"
```

**8e. The edges.**

```bash
uip maestro flow edge add DatastoreSimFlow.flow start addCustomers1
```

```bash
uip maestro flow edge add DatastoreSimFlow.flow addCustomers1 addOrders1
```

```bash
uip maestro flow edge add DatastoreSimFlow.flow addOrders1 ordersPerCustomer1
```

```bash
uip maestro flow edge add DatastoreSimFlow.flow ordersPerCustomer1 end1
```

**8f. Map the End node's outputs (the one hand edit).** Validate first, to see what's missing:

```bash
uip maestro flow validate DatastoreSimFlow.flow
```

**Check:** `"Status": "Valid"` with six `MISSING_OUTPUT_MAPPING` warnings. In the node
`"id": "end1"`, each output reads one node's field:

```json
"outputs": {
  "customers_added": { "source": "=js:$vars.addCustomers1.output.customers_added", "type": "number" },
  "customers_failed": { "source": "=js:$vars.addCustomers1.output.customers_failed", "type": "array" },
  "orders_added": { "source": "=js:$vars.addOrders1.output.orders_added", "type": "number" },
  "orders_rejected": { "source": "=js:$vars.addOrders1.output.orders_rejected", "type": "array" },
  "orders_failed": { "source": "=js:$vars.addOrders1.output.orders_failed", "type": "array" },
  "summary": { "source": "=js:$vars.ordersPerCustomer1.output.summary", "type": "array" }
}
```

The same edit with `jq`:

```bash
jq '(.nodes[] | select(.id == "end1")) |= (.outputs = {"customers_added": {"source": "=js:$vars.addCustomers1.output.customers_added", "type": "number"}, "customers_failed": {"source": "=js:$vars.addCustomers1.output.customers_failed", "type": "array"}, "orders_added": {"source": "=js:$vars.addOrders1.output.orders_added", "type": "number"}, "orders_rejected": {"source": "=js:$vars.addOrders1.output.orders_rejected", "type": "array"}, "orders_failed": {"source": "=js:$vars.addOrders1.output.orders_failed", "type": "array"}, "summary": {"source": "=js:$vars.ordersPerCustomer1.output.summary", "type": "array"}})' DatastoreSimFlow.flow > /tmp/datastore-flow.json
```

```bash
cp /tmp/datastore-flow.json DatastoreSimFlow.flow
```

**8g. Check, tidy, check again.**

```bash
uip maestro flow validate DatastoreSimFlow.flow
```

```bash
uip maestro flow format DatastoreSimFlow.flow
```

```bash
uip maestro flow validate DatastoreSimFlow.flow
```

**Check:** `"Status": "Valid"` both times, with no `Warnings`. `format` fills in
`variables.nodes`, which makes `$vars.<node>.output` resolve at run time: always run it.

### 9. Resources and pack

```bash
cd ..
```

```bash
uip solution resources refresh
```

**Check:** `"Status": "Synced 0 resources (0 already in solution)."`. `uip` 1.203.0 also prints
two `Warnings`, that the Function and Flow projects "were not checked for resource
contributions"; there are no resources here, so they change nothing.

```bash
uip solution pack . --dry-run
```

**Check:** `"Status": "Valid"`.

## What you end up with

```
datastore-simulation/
├── data/customers.json, data/orders.json      the input: 5 customers, 8 orders (one with no customer)
├── entities/
│   ├── DatastoreSimCustomer.create.json       the one side: CustomerCode unique
│   └── DatastoreSimOrder.create.json          the many side: Customer, the foreign key (IDs added by jq)
└── DatastoreSim/                              the Solution
    ├── DatastoreSim.uipx, resources/          tool-managed
    ├── DatastoreSimFunction/
    │   ├── keys.py, main.py, test_main.py     yours
    │   └── entry-points.json, bindings.json, uv.lock, …   generated
    └── DatastoreSimFlow/DatastoreSimFlow.flow the source; the .bpmn is generated from it
```

| Direction | Variable | Type |
|---|---|---|
| In | `customers` | array of `{customer_code, customer_name}`, default `[]` |
| In | `orders` | array of `{order_number, customer_code, amount}`, default `[]` |
| Out | `customers_added`, `orders_added` | number |
| Out | `customers_failed`, `orders_rejected`, `orders_failed` | array of strings |
| Out | `summary` | array of `{customer_code, customer_name, order_count, total_amount}` |

**Jobs per run:** 3, one per function node.

## Expected result

A run with the two data files, on empty entities:

| Output | Value |
|---|---|
| `customers_added` | 5 |
| `orders_added` | 7 |
| `orders_rejected` | `["O1005: no customer C999"]` |
| `customers_failed`, `orders_failed` | `[]` |

`summary`, sorted by customer code:

| `customer_code` | `customer_name` | `order_count` | `total_amount` |
|---|---|---|---|
| C001 | Gill Bates | 3 | 200.5 |
| C002 | Melon Eusk | 1 | 300.0 |
| C003 | Beff Jezos | 2 | 57.1 |
| C004 | Alice Wonderland | 0 | 0.0 |
| C005 | John Doe | 1 | 5.25 |

**The same run again:** `customers_added` 0 with 5 `customers_failed` (`CustomerCode` taken),
`orders_added` 0 with 7 `orders_failed` (`OrderNumber` taken), O1005 still rejected, and the same
summary. The unique keys make a repeated run harmless.

## Run it

[HOW_TO_RUN.md](HOW_TO_RUN.md) runs this simulation in four levels: the tests, a local run, the
tenant run (create the two entities, run the Flow, then query an order's customer and a customer's
orders), and a deployed run started over HTTP with curl or Postman. It also lists the things only
the tenant run can confirm.

## Try this

1. **Break the join.** In `keys.summarize`, skip customers with no orders (`if c["Id"] in count`).
   Four tests fail, and C004 disappears from the summary: what a `GROUP BY` on the orders alone
   would return.
2. **Store the code instead of the `Id`.** In `keys.resolve_orders`, put `order.customer_code` in
   `Customer`. Seven tests fail. On a tenant, Data Fabric itself refuses it: a `RELATIONSHIP` value
   must be a GUID (UiPath's Data Fabric skill, `records-query.md`, "Writing Choice-Set and
   Relationship Values").
3. **Drop the foreign key check.** Remove the `if customer_id is None` branch. Seven tests fail.
   Whether Data Fabric would catch a made-up `Id` is open: HOW_TO_RUN step 7 tries it.
4. **Add a customer later.** Add `{"customer_code": "C999", "customer_name": "Foo Bar"}` to the
   customers and run the Flow again: O1005 is accepted this time, and the 12 rows already there are
   refused as duplicates.
5. **Compare with Evelyn.** Evelyn's `hit_analytics` would be `DatastoreSimOrder` with a plain
   `STRING` `TransactionId` instead of the `RELATIONSHIP`. What would stop a hit pointing at an alert
   that doesn't exist? (In Evelyn: nothing but the code that writes it.)

## What building it taught

| Finding | Evidence | What was done |
|---|---|---|
| Evelyn declares no foreign keys | No `foreignKey`, `addForeignKeyConstraint` or `references` in migrations 030–046; no `@ManyToOne`, `@OneToMany` or `@JoinColumn` in any entity | The Evelyn table above. Its tables join on text columns in JPQL |
| A `RELATIONSHIP` field stores the parent's `Id`, whatever field it displays | UiPath's Data Fabric skill, `records-query.md`, "Writing Choice-Set and Relationship Values"; `uip df entities create --help` | `resolve_orders` looks the `Id` up first |
| The relationship needs the parent entity's `Id` and its display field's `Id` at create time | `RELATIONSHIP` takes `referenceEntityId` and `referenceFieldId` (`entity-schema.md`, "Relationship Fields") | The parent is created first, then `jq` fills both into the child's design |
| An `in` filter takes a `value_list` and refuses a `value` | The SDK's `EntityQueryFilter` validator (`uipath/platform/entities/entities.py:503-515`) | One customer lookup for every code |
| A Flow node sends `null` for a list input it doesn't set | `jq` on the nodes after 8c | `null_means_empty` in `DatastoreIn` |
| The Solution never learns about the entities | `find resources -type f` after step 7: only the function's package and process | HOW_TO_RUN step 3 creates them with `uip df` |
| The tests catch the rules that matter | Eight deliberate mistakes each failed at least one test | Listed in Status |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Fewer than `18 passed` | `keys.py`, `main.py` or the data changed | Read the failing test's name |
| `test_the_code_writes_exactly_the_entity_files_fields` fails | The code and `entities/*.create.json` name different fields | Make them agree |
| `echo "$FN"` prints nothing | A new terminal, or step 7 not done | Step 7, then 8b |
| `validate`: `MISSING_OUTPUT_MAPPING` | 8f not done | Do it |
| Node IDs end in `2` | A node added twice | Start again from step 1 in an empty folder |
| `ModuleNotFoundError: No module named 'keys'` | Run outside the function folder | Run from `DatastoreSimFunction/` |

## Done when

- [ ] `uv run pytest -q` passes (18).
- [ ] The local run (step 6) shows O1005 rejected, C004 with 0, and an order holding `id-of-C001`.
- [ ] The Flow `validate`s as Valid with no warnings, and `uip solution pack . --dry-run` is Valid.
- [ ] You can say which field is each entity's primary key, which is the foreign key, what value
  the foreign key holds, and why C004 needs a LEFT JOIN.
- [ ] **[On the tenant](HOW_TO_RUN.md#3-on-the-tenant):** the first run matches
  [Expected result](#expected-result), the query for Gill Bates's orders returns O1001, O1003 and
  O1007, and you've noted which rows of
  [Things only the tenant run can confirm](HOW_TO_RUN.md#things-only-the-tenant-run-can-confirm)
  turned out true.
