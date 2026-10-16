# How to run the Datastore Simulation

[README.md](README.md) explains what this simulates and builds it from an empty folder. This file
runs what's already here, in four levels. The first two need no tenant and take a minute.

| Level | Needs | Takes | Shows |
|---|---|---|---|
| [1. Tests](#1-tests) | `uv` | 1 minute | The key rules: the foreign key holds the `Id`, an unknown customer is refused, a customer with no orders still counts |
| [2. A local run](#2-a-local-run) | `uv` | 1 minute | The same rules on the data files, with made-up `Id`s |
| [3. On the tenant](#3-on-the-tenant) | `uip` logged in, a tenant | 15–25 minutes | The two entities, the Flow writing them, and the foreign key queried both ways |
| [4. Deployed, over HTTP](#4-deployed-and-started-over-http) | `uip` logged in, a tenant, a personal access token, `curl` or Postman | 30 minutes | The Solution deployed to its own folder and started by an HTTP call |

**Status:** levels 1 and 2 were run as written on 2026-10-16, and every check passed. Levels 3 and 4
haven't been run on a tenant yet.

## 0. Get it

```bash
git clone https://github.com/kowshik-narayanam/evelyn-simulations.git
```

```bash
cd "evelyn-simulations/Datastore Simulation"
```

The tools are listed in the repo's [README](../README.md#what-you-need). The first `uv run` in the
function project creates its `.venv` with Python 3.11 and the pinned packages.

## 1. Tests

```bash
cd DatastoreSim/DatastoreSimFunction
```

```bash
uv run pytest -q
```

**Check:** `18 passed`.

## 2. A local run

On the tenant the function reads and writes Data Fabric, which a laptop doesn't have. `keys.py`
holds the key rules with no SDK, and runs on the data files with made-up `Id`s. You're in
`DatastoreSimFunction`.

```bash
uv run python keys.py ../../data/customers.json ../../data/orders.json > /tmp/datastore-local.json
```

```bash
jq -c '.rejected' /tmp/datastore-local.json
```

**Check:** `["O1005: no customer C999"]`: the order whose customer doesn't exist.

```bash
jq -c '.order_rows[] | [.OrderNumber, .Customer]' /tmp/datastore-local.json
```

**Check:** seven orders, each holding its customer's `Id` (`id-of-C001`…), never the code.

```bash
jq -c '.summary[] | [.customer_code, .order_count, .total_amount]' /tmp/datastore-local.json
```

**Check:** the five lines of [Expected result](README.md#expected-result), C004 with `0` and `0.0`.

Go back to the simulation folder for level 3:

```bash
cd ../..
```

## 3. On the tenant

**Needs a tenant login; not run yet.** These steps create two Data Fabric entities on the tenant
you're logged into, run the Flow twice (three jobs each) and use about 40 Data Fabric API calls. A
Community tenant allows 1,000 a day. Use a tenant you're allowed to experiment on.

**1. Check the login and that the names are free.**

```bash
uip login status
```

```bash
uip df entities list --native-only --output json --output-filter "[?Name=='DatastoreSimCustomer' || Name=='DatastoreSimOrder'].Name"
```

**Check:** `[]`. If a name is listed, it was created before: skip its `create` below, and set its
variable with the `=$( … )` line instead.

**2. The customer entity, the one side, first.** The orders' foreign key has to point at it.

```bash
uip df entities create DatastoreSimCustomer --file entities/DatastoreSimCustomer.create.json
```

```bash
CUSTOMER_ENTITY_ID=$(uip df entities list --native-only --output plain --output-filter "[?Name=='DatastoreSimCustomer'].Id | [0]")
```

```bash
CUSTOMER_CODE_FIELD=$(uip df entities get "$CUSTOMER_ENTITY_ID" --output plain --output-filter "Fields[?Name=='CustomerCode'].Id | [0]")
```

`CUSTOMER_CODE_FIELD` is the field the relationship **displays**: the Data Fabric UI shows an
order's customer as `C001`. The stored value is still the customer row's `Id`.

**3. The order entity, the many side,** with the two IDs filled into a copy of its design:

```bash
jq --arg e "$CUSTOMER_ENTITY_ID" --arg f "$CUSTOMER_CODE_FIELD" '(.fields[] | select(.name == "Customer")) += {"referenceEntityId": $e, "referenceFieldId": $f}' entities/DatastoreSimOrder.create.json > /tmp/DatastoreSimOrder.json
```

```bash
uip df entities create DatastoreSimOrder --file /tmp/DatastoreSimOrder.json
```

```bash
ORDER_ENTITY_ID=$(uip df entities list --native-only --output plain --output-filter "[?Name=='DatastoreSimOrder'].Id | [0]")
```

```bash
echo "$CUSTOMER_ENTITY_ID | $CUSTOMER_CODE_FIELD | $ORDER_ENTITY_ID"
```

**Check:** three GUIDs, and both `create` commands said `"Code": "EntityCreated"`.

**4. See the keys in the schema.**

```bash
uip df entities get "$ORDER_ENTITY_ID" --output json --output-filter "Fields[].{name: Name, type: FieldDataType.Name, required: IsRequired, unique: IsUnique}"
```

```bash
uip df entities get "$ORDER_ENTITY_ID" --output json --output-filter "Fields[?Name=='Customer'] | [0].{points_at: ReferenceEntity.Id, displays: ReferenceField.Id}"
```

**Check:** `Id` and the system fields next to your three; `OrderNumber` unique; `Customer` of type
relationship, required. `points_at` equals `$CUSTOMER_ENTITY_ID` and `displays` equals
`$CUSTOMER_CODE_FIELD`. The field names in these filters come from UiPath's Data Fabric skill
(`entity-schema.md`, "Round-trip"), not from a run: if a column prints `null`, drop
`--output-filter` and read `Fields`. In the browser, Data Fabric → Entities → Datastore Sim Order
shows `Customer` as a relationship to Datastore Sim Customer.

**5. Run the Flow.** The Flow's two inputs come from the data files:

```bash
jq -n --slurpfile c data/customers.json --slurpfile o data/orders.json '{customers: $c[0], orders: $o[0]}' > /tmp/datastore-inputs.json
```

```bash
cd DatastoreSim
```

```bash
uip maestro flow debug DatastoreSimFlow --inputs "$(cat /tmp/datastore-inputs.json)" --output json > /tmp/datastore-debug-1.json
```

It packs the Solution, uploads it to Studio Web and runs it once: three jobs, 2 to 6 minutes, and
it prints only at the end.

```bash
jq '.Data.finalStatus' /tmp/datastore-debug-1.json
```

```bash
jq '.Data' /tmp/datastore-debug-1.json
```

**Check:** not `Faulted`, and the outputs match [Expected result](README.md#expected-result). In
Maestro's instance view, open **Add customers**: its `customer_ids` output lists each code with the
`Id` Data Fabric assigned. If the run faulted, the cause is in the same file:

```bash
jq -r '.Data.variables.elements[] | select(.outputs.Error) | "\(.elementId) \(.outputs.Error.detail)"' /tmp/datastore-debug-1.json
```

**6. Query the foreign key, both ways.** First, one customer's `Id` from its business key:

```bash
GILL_ID=$(uip df records query "$CUSTOMER_ENTITY_ID" --limit 100 --body '{"filterGroup": {"logicalOperator": 0, "queryFilters": [{"fieldName": "CustomerCode", "operator": "=", "value": "C001"}]}}' --output plain --output-filter "Items[0].Id")
```

**A customer's orders**, `WHERE Customer = <Gill's Id>`:

```bash
uip df records query "$ORDER_ENTITY_ID" --limit 100 --body "{\"filterGroup\": {\"logicalOperator\": 0, \"queryFilters\": [{\"fieldName\": \"Customer\", \"operator\": \"=\", \"value\": \"$GILL_ID\"}]}}" --output json --output-filter "Items[].OrderNumber"
```

**Check:** O1001, O1003 and O1007, in some order.

**An order's customer:** read O1004's `Customer`, then fetch that customer row by its primary key:

```bash
O1004_CUSTOMER=$(uip df records query "$ORDER_ENTITY_ID" --limit 100 --body '{"filterGroup": {"logicalOperator": 0, "queryFilters": [{"fieldName": "OrderNumber", "operator": "=", "value": "O1004"}]}}' --output plain --output-filter "Items[0].Customer")
```

```bash
echo "$O1004_CUSTOMER"
```

```bash
uip df records get "$CUSTOMER_ENTITY_ID" "$O1004_CUSTOMER" --output json --output-filter "{code: CustomerCode, name: CustomerName}"
```

**Check:** the `echo` prints a GUID (not `C002`), and the record is C002 Melon Eusk. If the `echo`
prints an object instead, the read returned the parent row: write what you saw in the table below.

**7. Try: does Data Fabric enforce the foreign key?** The function refuses an unknown customer
before writing. Here you go round it, with an `Id` no customer has:

```bash
uip df records insert "$ORDER_ENTITY_ID" --body '{"OrderNumber": "O9999", "Customer": "00000000-0000-0000-0000-000000000000", "Amount": 1}' --output json
```

**Check:** either a refusal (Data Fabric checks the parent exists) or a new record (it only checks
the value is a GUID). Write which in [Things only the tenant run can confirm](#things-only-the-tenant-run-can-confirm).
If it was accepted, delete it:

```bash
O9999_ID=$(uip df records query "$ORDER_ENTITY_ID" --limit 100 --body '{"filterGroup": {"logicalOperator": 0, "queryFilters": [{"fieldName": "OrderNumber", "operator": "=", "value": "O9999"}]}}' --output plain --output-filter "Items[0].Id")
```

```bash
uip df records delete "$ORDER_ENTITY_ID" "$O9999_ID" --yes --reason "Datastore Simulation: foreign key test row"
```

**8. Run the Flow again.**

```bash
uip maestro flow debug DatastoreSimFlow --inputs "$(cat /tmp/datastore-inputs.json)" --output json > /tmp/datastore-debug-2.json
```

```bash
jq '.Data' /tmp/datastore-debug-2.json
```

**Check:** `customers_added` 0 with five `customers_failed`, `orders_added` 0 with seven
`orders_failed`, O1005 still in `orders_rejected`, and the same `summary`. The unique keys refused
every duplicate. Copy one `customers_failed` line into the table below: it is Data Fabric's real
wording for a unique-key refusal.

- **A new terminal forgets the variables.** Re-run the `=$( … )` lines of steps 2, 3 and 6.
- **Don't run `uipath auth` in the function folder.** `uip solution pack`, which `flow debug` also
  uses, ships `.env` inside the package. `uip login` keeps its login in `~/.uipath/`.
- **If a node fails with a 401 or 403:** the identity its job runs as has no Data Fabric role. In
  Data Fabric → Manage Access, give it **Data Writer** (**Inference**: a debug run's jobs run as you).
- **Run either this folder or your rebuild on the tenant, not both.** They use the same function,
  Flow and entity names, and names are tenant-wide.

## 4. Deployed, and started over HTTP

**Untested.** Nobody has run this level yet. It's written from the `uip` CLI's help and from the
Orchestrator API docs. It deploys the Solution into an Orchestrator folder of its own, then starts
the Flow with an HTTP call, the way another system would.

The two entities are tenant-level, not part of the Solution, so the deployed functions use the same
ones level 3 filled (**Inference**). A deployed run after level 3 therefore gives the second-run
result of step 8.

Start from the simulation folder.

**1. Pack and publish.**

```bash
cd DatastoreSim
```

```bash
uip solution resources refresh
```

```bash
uip solution pack . /tmp/datastore-pack --version 1.0.0 --output json
```

```bash
uip solution publish /tmp/datastore-pack/DatastoreSim_1.0.0.zip --output json
```

**Check:** `uip solution packages list --name DatastoreSim --output json` lists version `1.0.0`.
To publish again after a change, pack with a higher `--version`.

**2. Deploy** into a new folder, `DatastoreSim Deployed`:

```bash
uip solution deploy run -n datastore-sim --package-name DatastoreSim --package-version 1.0.0 --folder-name "DatastoreSim Deployed" --output json
```

**Check:** `Status` is `DeploymentSucceeded`. If the folder name is taken, the deploy picks
another; step 4 finds it either way.

**3. A token for the HTTP calls.** In UiPath, select your user icon → **Preferences** → **Personal
access token** → **Generate new token**, with the **Orchestrator** scopes `OR.Jobs`, `OR.Execution`
and `OR.Folders.Read` (**Inference** on the last one's name). It's shown once. Read it into the
shell without echoing it:

```bash
read -s TOKEN
```

Then the API's base URL. Replace `<org>` and `<tenant>` with the first two parts of the path in your
Orchestrator URL:

```bash
BASE="https://cloud.uipath.com/<org>/<tenant>/orchestrator_"
```

**4. Find the folder and the Flow's release key.**

```bash
FOLDER_ID=$(curl -s --get "$BASE/odata/Folders" --data-urlencode "\$filter=contains(DisplayName,'DatastoreSim')" --data-urlencode '$select=Id' -H "Authorization: Bearer $TOKEN" | jq -r '.value[0].Id')
```

```bash
RELEASE_KEY=$(curl -s --get "$BASE/odata/Releases" --data-urlencode "\$filter=Name eq 'DatastoreSimFlow'" --data-urlencode '$select=Key' -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq -r '.value[0].Key')
```

```bash
echo "$FOLDER_ID | $RELEASE_KEY"
```

**Check:** a number and a GUID. `null` means the filter matched nothing: run the `curl` without
`| jq -r …` and read the response.

**5. Start it.** `InputArguments` holds the Flow's inputs as a JSON **string**, so `jq` builds the
body from the data files:

```bash
jq -n --arg k "$RELEASE_KEY" --slurpfile c ../data/customers.json --slurpfile o ../data/orders.json '{startInfo: {ReleaseKey: $k, RunAsMe: true, InputArguments: ({customers: $c[0], orders: $o[0]} | tojson)}}' > /tmp/datastore-start-job.json
```

```bash
JOB_ID=$(curl -s -X POST "$BASE/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" -H "Content-Type: application/json" -d @/tmp/datastore-start-job.json | jq -r '.value[0].Id')
```

```bash
echo "$JOB_ID"
```

**Check:** a job number.

**6. Poll until it ends**, every 10 seconds for up to 10 minutes:

```bash
for i in $(seq 60); do STATE=$(curl -s "$BASE/odata/Jobs($JOB_ID)" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq -r .State); echo "$STATE"; case "$STATE" in Successful|Faulted|Stopped) break;; esac; sleep 10; done
```

**Check:** it ends with `Successful`. If it's still `Running` after 5 minutes, open the run in
Maestro → **Flow instances** and read its incident.

**7. Read the result.** `OutputArguments` is a JSON string too:

```bash
curl -s "$BASE/odata/Jobs($JOB_ID)" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq '.OutputArguments | fromjson?'
```

**Check:** after level 3, the second-run result of step 8; on fresh entities,
[Expected result](README.md#expected-result).

**8. Remove the deployment** when you're done. The entities stay; [Clean up](#clean-up) removes them.

```bash
uip solution deploy uninstall datastore-sim --yes
```

### The same calls in Postman

1. **An environment** with five variables: `base` (the `BASE` above), `folderId`, `releaseKey`,
   `jobId`, and `token` with type **secret**. Put the token in **Current value** only: Postman
   syncs initial values to its cloud, and current values stay on your machine.
2. **A collection** whose **Authorization** tab is **Bearer Token** with `{{token}}`.
3. **Four requests:**

| Request | Method and URL | Extra headers |
|---|---|---|
| Find the folder | `GET {{base}}/odata/Folders?$filter=contains(DisplayName,'DatastoreSim')` | None |
| Find the release | `GET {{base}}/odata/Releases?$filter=Name eq 'DatastoreSimFlow'` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |
| Start | `POST {{base}}/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs` | The same, plus `Content-Type: application/json` |
| Poll | `GET {{base}}/odata/Jobs({{jobId}})` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |

4. **The Start request's body** (raw, JSON): the contents of `/tmp/datastore-start-job.json` from
   step 5, with the release key replaced by `{{releaseKey}}`. `InputArguments` is a string, so its
   quotes are escaped.
5. **Save the job's Id** for the Poll request: in the Start request's **Scripts** →
   **Post-response**, add:

```js
pm.environment.set("jobId", pm.response.json().value[0].Id);
```

Don't export or share the environment: it holds your token.

## Where to look in the browser

| To see | Go to |
|---|---|
| The two entities, their fields and their rows | Data Fabric → **Entities** → Datastore Sim Customer / Datastore Sim Order. The order's `Customer` column shows the customer's code, the display field; the stored value is the `Id` |
| One run, node by node | The Studio Web link in the debug output: `jq -r '.Data.studioWebUrl' /tmp/datastore-debug-1.json`. Click a node to see its input and output; **Incidents** holds the error |
| Every Flow run | Maestro → **Flow instances** (Preview). Whether debug runs show up there is unverified |
| Each function's job | Orchestrator → **My Workspace** → **Automations** → **Jobs**: one job per function node (**Inference**) |

## Things only the tenant run can confirm

| Unknown | Why it matters | Where it's tested | What you saw |
|---|---|---|---|
| Does Data Fabric refuse a `Customer` that points at no customer row? | Whether the foreign key is enforced, or only typed | Step 7 | |
| What happens to a customer's orders when the customer row is deleted: refused, orders deleted, or orders left pointing at nothing? | Deleting data safely | Not scripted: delete C005 John Doe in the browser, then look at O1008 | |
| Does a read return `Customer` as the bare `Id`, or as the customer's row? | `main._row` handles both; the doc says the `Id` | Step 6, the `echo` | |
| Data Fabric's wording for a unique-key refusal | Error handling | Step 8 | |
| Do a debug run's jobs reach Data Fabric as you, with no role to add? | Every write | Step 5 | |
| Does a batch insert return each new row's fields, so `customer_ids` is filled? | The `customer_ids` output only | Step 5, **Add customers** output | |

## When a run fails

1. Open the Studio Web link (`jq -r '.Data.studioWebUrl' <the debug json>`), then **Incidents**. It
   names the node and the error.
2. Look up the error in [Troubleshooting](README.md#troubleshooting).
3. Check [Things only the tenant run can confirm](#things-only-the-tenant-run-can-confirm): nobody
   has run this on a tenant yet. Record what you find there, and drop the **Inference** label from
   the README once it's confirmed.

## Clean up

The entities stay until you delete them, and deleting one deletes its records. Delete the orders
entity before the customers entity: it holds the foreign key.

```bash
uip df entities delete "$ORDER_ENTITY_ID" --yes --reason "Datastore Simulation clean-up"
```

```bash
uip df entities delete "$CUSTOMER_ENTITY_ID" --yes --reason "Datastore Simulation clean-up"
```
