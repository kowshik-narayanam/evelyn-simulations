# Configuration simulation: a Flow driven by configuration.json

**The point of this example:** Evelyn reads almost everything it does from its configuration:
where the alerts come from (`INPUT_TYPE`), which screening provider to call (`PROVIDER_ID`),
thresholds, reports. This example does the same with a toy worker, a calculator. Its four
operators stand in for Evelyn's providers. One setting picks the operator, and the Flow's **Switch**
sends the run to that operator's node.

- **The form:** `configuration.json` lists every setting: its key, label, type, allowed values and
  default. It ships inside the function package.
- **The saved values:** `configuration_payload.json`, in a storage bucket, holds only what an
  administrator changed.
- **The run's overrides:** any setting can be changed for one run, from the Flow's input.
- **The secret:** the API key isn't in the configuration. The configuration names an Orchestrator
  **Credential asset**, and only the calculator node reads it.

```
CalcConfigFlow
  Manual trigger ─► Load configuration ─► Read numbers ─► Which calculator? ─ADD──────► Add ───────┐
  overrides,        the form's defaults,   CSV: from the   a Switch on        ─SUBTRACT─► Subtract ──┤
  numbers           the saved payload,     bucket          PROVIDER_ID        ─MULTIPLY─► Multiply ──┤
                    the run's overrides    API: from the                      ─DIVIDE───► Divide ────┤
                    out: config,           trigger                                                   │
                    provider_id, ...       out: numbers         each calculator writes `calculation` │
                                                                                                     ▼
                                                        CSV report on? ─true─► Write report ─► End
                                                              └──false───────────────────────► End
```

End outputs: `provider_id`, `alert_count`, `report_path`, `overridden_keys` and `calculation`.

| Evelyn (WorkFusion) | Here |
|---|---|
| `configuration.json`, the Form.io page in `names-screening-package/src/main/resources/` | `CalcConfigFunction/configuration.json`: a flat list of fields with Evelyn's `key`, `label`, `type`, `values` and `defaultValue` |
| `configuration_payload.json` (`INPUT_TYPE: SCREENING_SYSTEM`, `PROVIDER_ID: FACTIVA`, lines 3–4), and what Control Tower saves for the worker | `config/configuration_payload.json` in the bucket `CalcConfigFiles`. It holds only the changed keys |
| `TaskConfigurationProvider.getDigitalWorkerConfiguration()`, called by each task processor (23 files in `names-screening-jnw`, e.g. `CsvTaskProcessor.java:49`) | The node **Load configuration**, once per run. Later nodes get its `config` as an input |
| Dotted keys such as `configuration.reports.csv.enable` | The same keys, nested in `config`: `$vars.loadConfiguration1.output.config.configuration.reports.csv.enable` |
| `INPUT_TYPE` radio: `SCREENING_SYSTEM`, `API`, `CSV` (`configuration.json:61`) | `INPUT_TYPE`: `CSV` or `API`. **Read numbers** picks the source in code. **Inference:** a real port gives each input type its own trigger |
| `PROVIDER_ID` select: `FACTIVA`, `WORLD_CHECK_ONE`, `FIRCO_TRUST`, `TR_CLEAR_API` (`configuration.json:94`) | `PROVIDER_ID` select: `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, and the Switch **Which calculator?** |
| One connector per provider | One calculator node per operator |
| Provider settings, e.g. `provider.FACTIVA_HITS_PER_PAGE` | `provider.DIVIDE_ON_ZERO`, `provider.ROUND_TO` |
| A secret inside the configuration: `enrichment.location.apiKey` (`configuration.json:1230`) | Only the asset's name, `provider.API_KEY_ASSET`. The key itself is in the Credential asset `CalcApiKey` |
| `model.thresholds.name_strong_match` (`configuration.json:1914`) | `model.thresholds.alert_above` |
| `configuration.reports.csv.enable`, `configuration.resulting_path` (`configuration.json:3075, 3569`) | The same keys, and the Decision **CSV report on?** |
| BP variables | The Flow's `inout` global `calculation` |

Evelyn line numbers are from `names-screening` `master` @ `6dcf7f9d3` (2026-09-24). The model repo
`nss-classification-model` isn't used here.

**Status (2026-10-15):**
- **Verified locally:**
  - the build commands below, re-run as written in an empty folder;
  - 32 tests pass;
  - nine deliberately wrong rules each fail the tests: `round()` instead of half-up, the layers in
    the wrong order, unknown keys ignored, `true` accepted as a number, an alert at the threshold,
    `DIVIDE_ON_ZERO` ignored, no provider check, an empty API key accepted, `INPUT_TYPE` ignored;
  - the Flow `validate`s as Valid with no warnings;
  - `solution pack` is Valid, and a real pack puts `configuration.json` inside the function's
    package.
- **Not run yet:** the tenant run. Nothing in this folder has been uploaded or run on a tenant.

## How the configuration works

| What | Where it lives | Who changes it |
|---|---|---|
| The form, `configuration.json` | Inside `CalcConfigFunction`, so inside its package | Developers, with a new version |
| The saved values, `configuration_payload.json` | The bucket `CalcConfigFiles`, at `config/configuration_payload.json` | An administrator, by uploading a new file. No redeploy |
| The run's overrides | The Flow's input `overrides` | Whoever starts the run |
| The API key | The Credential asset `CalcApiKey` | An administrator, in Orchestrator's **Assets** |

**Three layers, a later one winning key by key:** the form's `defaultValue`s, then the saved
payload, then the run's overrides. This repo's payload changes three settings:

```json
{
  "configuration": { "INPUT_TYPE": "CSV", "PROVIDER_ID": "DIVIDE" },
  "provider": { "DIVIDE_ON_ZERO": "SKIP_ROW" }
}
```

Every other setting comes from the form: `ROUND_TO` 2, `alert_above` 100, the report on.

**Every value is checked against the form,** at load time:
- an unknown key fails and lists the known ones;
- a `radio` or `select` value must be one of the field's `values`;
- a `number` must be in its `validate` range, and whole when `integer` is set;
- a `checkbox` must be `true` or `false`, and a `textfield` must hold some text.

So `"PROVIDER_ID": "DIVDE"` stops the run at **Load configuration** and names the allowed values,
instead of failing five nodes later.

**Why load once and pass it along.** Each function node is a separate Orchestrator job. Reading the
file in every node would cost a bucket download per job. Worse, an administrator could upload a new
file during a run, and the run would mix two configurations. Loading once gives each run one
snapshot, visible in the instance view as **Load configuration**'s output.

**How the Flow knows which calculator ran.** A Switch's own outputs (`matchedCase`) are never set at
run time, so a node after the Switch can't ask it. Instead, each calculator node writes its output
into the Flow's `inout` global `calculation` (a **variable update**), and **Write report** and
**End** read `$vars.calculation`. The four branches join by all pointing at the same next node; a
**Merge** node would wait for all four and hang. (Both rules are from UiPath's Maestro Flow skill:
`switch/impl.md`, `merge/planning.md`, `decision/impl.md`.)

## Build it yourself

Every command below, in order, builds this example from an empty folder. The code files are
copied from this folder; type them yourself if you prefer.

- **Start here:** open a terminal in this folder, the one with this README. Step 1 remembers it as
  `$EXAMPLE`.
- **Where:** the commands build in `~/rebuild/config-simulation`. Change the path in step 1 if you
  like; everything after it is relative.
- **One terminal:** run every block in the same terminal, top to bottom. `$EXAMPLE` (step 1) and the
  function's node type (step 7) live in shell variables, and a new terminal forgets them.
- **Local only:** nothing in steps 1–8 changes the tenant. `uip maestro flow validate`, `registry`
  and `uip solution resources refresh` read from the tenant you're logged into, read only.
- **Different IDs:** your Solution, projects and function get new IDs. Your `.flow` matches this
  folder's except for those keys.
- **Needs:** `uv`, the `uip` CLI (logged in: `uip login status`) and `jq`.

| Build step | Section |
|---|---|
| The folder, the Solution, the function project | [1](#1-the-folder-and-the-input-files)–[3](#3-the-function-project) |
| The code, the tests, the bindings, a local run | [4](#4-the-code)–[5](#5-tests-schema-bindings-and-a-local-run) |
| The Credential asset, then register the function | [6](#6-the-credential-asset-and-the-function) |
| The Flow | [7](#7-the-flow-calcconfigflow) |
| `resources refresh`, then `pack --dry-run` | [8](#8-resources-and-pack) |

### 1. The folder and the input files

```bash
EXAMPLE=$(pwd)
```

```bash
mkdir -p ~/rebuild/config-simulation/data
```

```bash
cd ~/rebuild/config-simulation
```

```bash
cp "$EXAMPLE"/data/{numbers.csv,configuration_payload.json} data/
```

`data/` lives outside the Solution, so no package ships it; on the tenant you upload both files to
the bucket.

| Row | ID | a | b | Why it's there |
|---|---|---|---|---|
| 1 | N-01 | 250 | 2 | Above 100 for every operator: one alert each |
| 2 | N-02 | 12 | 9 | Above 100 only when multiplied (108) |
| 3 | N-03 | -7.5 | 2.5 | Negatives and decimals |
| 4 | N-04 | 2.01 | 2 | The rounding trap: 2.01 / 2 prints as 1.005, and `round()` makes it 1.0, not 1.01 |
| 5 | N-05 | 42 | 0 | Division by zero: `DIVIDE_ON_ZERO` decides |
| 6 | N-06 | 1 | 3 | A repeating decimal, rounded to `ROUND_TO` places |
| 7 | N-07 | 50 | 2 | Multiplied, exactly 100: on the threshold, so **not** an alert |

**Check:** `head -3 data/numbers.csv` shows `id,a,b`, then `N-01,250,2` and `N-02,12,9`.

### 2. The Solution

```bash
uip solution init CalcConfig
```

**Check:** `ls CalcConfig` shows `AGENTS.md`, `CLAUDE.md` and `CalcConfig.uipx`. Those
`AGENTS.md`/`CLAUDE.md` are `uip`'s generated notes, not this example's: its own are at the
example root.

### 3. The function project

```bash
cd CalcConfig
```

```bash
mkdir CalcConfigFunction
```

```bash
cd CalcConfigFunction
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
uv run uipath new CalcConfigFunction --type function
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

One function project, not one per operator: the four calculators are four **nodes** of the same
function, each with its `operation` fixed, so the configuration code lives in one place.

### 4. The code

```bash
cp "$EXAMPLE"/CalcConfig/CalcConfigFunction/{main.py,settings.py,calculator.py,configuration.json,test_main.py} .
```

| File | Holds |
|---|---|
| `configuration.json` | The form: nine settings with key, label, type, allowed values and default |
| `settings.py` | `load(saved, overrides)`: the three layers, each value checked against the form. `report_path`: `resulting_path` with `{year}`/`{month}` filled in. Pure Python: no bucket |
| `calculator.py` | `parse_numbers` (header `id,a,b`, a bad row fails with its line number), `calculate` (the operator, `DIVIDE_ON_ZERO`, half-up rounding, the alert) and `to_csv`. Pure Python |
| `main.py` | Seven operations, one per node: `load_configuration`, `read_numbers`, `add`, `subtract`, `multiply`, `divide`, `write_report`. The bucket and the Credential asset are read here |
| `test_main.py` | 32 tests, with a fake bucket and a fake asset in place of the SDK |

**Check:** `ls` shows the five files next to `pyproject.toml` and `uipath.json`.

### 5. Tests, schema, bindings, and a local run

```bash
uv run pytest -q
```

**Check:** `32 passed`.

```bash
uv run uipath init
```

`uipath init` writes `entry-points.json`, `bindings.json`, `main.mermaid` and more: all generated.

**The bindings (a hand edit).** `bindings.json` tells the Solution which Orchestrator resources the
function uses. `uipath init` leaves it empty, so add the bucket and the asset. The asset's
`"SubType": "credentialAsset"` records what kind it is; step 6 explains why it isn't enough on its
own.

```bash
jq '.resources = [{"resource": "bucket", "key": "CalcConfigFiles", "value": {"name": {"defaultValue": "CalcConfigFiles", "isExpression": false, "displayName": "Name"}, "folderPath": {"defaultValue": "", "isExpression": false, "displayName": "Folder Path"}}, "metadata": {"ActivityName": "download", "BindingsVersion": "2.2", "DisplayLabel": "FullName"}}, {"resource": "asset", "key": "CalcApiKey", "value": {"name": {"defaultValue": "CalcApiKey", "isExpression": false, "displayName": "Name"}, "folderPath": {"defaultValue": "", "isExpression": false, "displayName": "Folder Path"}}, "metadata": {"ActivityName": "retrieve_credential", "BindingsVersion": "2.2", "DisplayLabel": "FullName", "SubType": "credentialAsset"}}]' bindings.json > bindings.json.tmp
```

```bash
mv bindings.json.tmp bindings.json
```

**Check:** `jq -c '.resources[] | {resource, key}' bindings.json` prints the bucket
`CalcConfigFiles` and the asset `CalcApiKey`.

**A local run.** The function's operations need the bucket and the asset, so locally you call the
pure modules directly. First, the three layers. This merges the saved payload with an override for
one run:

```bash
uv run python -c "import json, settings; c = settings.load(json.load(open('../../data/configuration_payload.json')), {'configuration': {'PROVIDER_ID': 'MULTIPLY'}}); print(c['configuration']['PROVIDER_ID'], c['provider'])"
```

**Check:** `MULTIPLY {'DIVIDE_ON_ZERO': 'SKIP_ROW', 'ROUND_TO': 2, 'API_KEY_ASSET': 'CalcApiKey'}`.
The override won; `DIVIDE_ON_ZERO` came from the payload, the rest from the form.

Then the calculation **Load configuration**, **Read numbers** and **Divide** do on the tenant, with
the saved payload alone:

```bash
uv run python -c "import json, settings, calculator; c = settings.load(json.load(open('../../data/configuration_payload.json')), None); print(calculator.to_csv(calculator.calculate(c['configuration']['PROVIDER_ID'], calculator.parse_numbers(open('../../data/numbers.csv').read()), c)))"
```

**Check:** the report in [Expected result](#expected-result).

Finally, a typo, which fails on purpose:

```bash
uv run python -c "import settings; settings.load({'configuration': {'PROVIDER_ID': 'DIVDE'}}, None)"
```

**Check:** the last line is `ValueError: configuration.PROVIDER_ID is 'DIVDE'; allowed: ADD,
SUBTRACT, MULTIPLY, DIVIDE`, and the command exits with an error. That is the message the tenant
run shows at **Load configuration**.

### 6. The Credential asset and the function

```bash
cd ..
```

```bash
uip solution resources add --source local --kind Asset --name CalcApiKey --type credentialAsset
```

```bash
uip solution projects add ./CalcConfigFunction
```

**Check:** `find resources -type f` lists four files:
- `asset/credentialAsset/CalcApiKey.json`, with `"type": "Credential"` in its `spec`;
- `bucket/orchestratorBucket/CalcConfigFiles.json`;
- one in `package/` and one in `process/function/`.

**Why the asset comes first, and with that `--type`.** `projects add` creates a resource for each
binding, but it ignores the binding's `SubType` and makes a plain **Text** asset
(`asset/stringAsset/`). Declaring the Credential asset first makes `projects add` find it and leave
it alone. `--type Credential` doesn't work either: it is accepted and silently makes a Text asset.
Only `credentialAsset` gives a Credential (checked 2026-10-15).

The asset and the bucket are **virtual**: they live in `solution_folder`, and the Solution creates
them when it's deployed or debug-run. The asset arrives without a value, so it is set on the
tenant (tenant step 4).

### 7. The Flow: CalcConfigFlow

**7a. Create the Flow project.** From `CalcConfig/` (you're there):

```bash
uip maestro flow init CalcConfigFlow
```

**Check:** the output shows `"Status": "Registered"`.

```bash
cd CalcConfigFlow
```

**7b. Keep the function's node type in a shell variable.** `registry search --local` returns two
types per function: the function node and an agent-tool node. The filter picks the function
node by its `Category`.

```bash
FN=$(uip maestro flow registry search CalcConfigFunction --local --output plain --output-filter "[?DisplayName=='CalcConfigFunction' && Category=='function'].NodeType | [0]")
```

**Check:** `echo $FN` prints `uipath.core.function.…`.

**7c. The nodes.** A node's ID comes from its label: `Load configuration` becomes
`loadConfiguration1`.

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Load configuration" --input '{"operation": "load_configuration", "overrides": "=js:$vars.start.output.overrides", "config_path": "config/configuration_payload.json"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Read numbers" --input '{"operation": "read_numbers", "config": "=js:$vars.loadConfiguration1.output.config", "numbers": "=js:$vars.start.output.numbers"}'
```

The Switch: one case per `PROVIDER_ID` value. A case's `id` names its output port, `case-<id>`.

```bash
uip maestro flow node add CalcConfigFlow.flow core.logic.switch --label "Which calculator?" --input '{"cases": [{"id": "add", "label": "ADD", "expression": "$vars.loadConfiguration1.output.provider_id === \"ADD\""}, {"id": "subtract", "label": "SUBTRACT", "expression": "$vars.loadConfiguration1.output.provider_id === \"SUBTRACT\""}, {"id": "multiply", "label": "MULTIPLY", "expression": "$vars.loadConfiguration1.output.provider_id === \"MULTIPLY\""}, {"id": "divide", "label": "DIVIDE", "expression": "$vars.loadConfiguration1.output.provider_id === \"DIVIDE\""}]}'
```

The four calculators: the same node type, a different fixed `operation`.

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Add" --input '{"operation": "add", "config": "=js:$vars.loadConfiguration1.output.config", "numbers": "=js:$vars.readNumbers1.output.numbers"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Subtract" --input '{"operation": "subtract", "config": "=js:$vars.loadConfiguration1.output.config", "numbers": "=js:$vars.readNumbers1.output.numbers"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Multiply" --input '{"operation": "multiply", "config": "=js:$vars.loadConfiguration1.output.config", "numbers": "=js:$vars.readNumbers1.output.numbers"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Divide" --input '{"operation": "divide", "config": "=js:$vars.loadConfiguration1.output.config", "numbers": "=js:$vars.readNumbers1.output.numbers"}'
```

The Decision, the report and the End:

```bash
uip maestro flow node add CalcConfigFlow.flow core.logic.decision --label "CSV report on?" --input '{"expression": "$vars.loadConfiguration1.output.report_enabled", "trueLabel": "Write it", "falseLabel": "Skip it"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow "$FN" --label "Write report" --input '{"operation": "write_report", "results": "=js:$vars.calculation.results", "report_path": "=js:$vars.loadConfiguration1.output.report_path"}'
```

```bash
uip maestro flow node add CalcConfigFlow.flow core.control.end --label "End"
```

| Node ID | Reads | Why |
|---|---|---|
| `loadConfiguration1` | `overrides` ← the trigger | Layer 3. The payload path is fixed on the node |
| `readNumbers1` | `config`, and `numbers` ← the trigger | `INPUT_TYPE` CSV reads `DATA_FILE_LOCATION` from the bucket; API uses the trigger's numbers |
| `whichCalculator1` | `provider_id` | One case per operator. No `default` case: Load configuration only lets the four values through |
| `add1` … `divide1` | `config`, `numbers` ← Read numbers | Each checks that `PROVIDER_ID` is its own operator, reads the API key, calculates |
| `csvReportOn1` | `report_enabled` | `configuration.reports.csv.enable` |
| `writeReport1` | `results` ← `$vars.calculation`, `report_path` | Whichever calculator ran wrote `calculation` (7f) |

Inputs you don't set are sent as `null` or `""`, and `main.py` reads both as "the default".

**7d. The Flow's inputs, outputs and the global.**

```bash
uip maestro flow variable add CalcConfigFlow.flow overrides --direction in --type object --default-value '{}' --description "Settings for this run only, laid over the saved payload key by key, e.g. {\"configuration\": {\"PROVIDER_ID\": \"MULTIPLY\"}}"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow numbers --direction in --type array --sub-type object --default-value '[]' --description "The pairs to calculate when INPUT_TYPE is API: id, a, b"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow calculation --direction inout --type object --default-value '{}' --description "The output of whichever calculator ran: provider_id, results, alert_count"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow provider_id --direction out --type string --description "The calculator this run used"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow alert_count --direction out --type number --description "How many results were above model.thresholds.alert_above"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow report_path --direction out --type string --description "Where the CSV report went inside the bucket; empty when the report is off"
```

```bash
uip maestro flow variable add CalcConfigFlow.flow overridden_keys --direction out --type array --sub-type string --description "The settings this run overrode, as dotted keys"
```

**7e. The edges.** The Switch's edges leave from its case ports, and all four calculators point at
the same Decision: that is the join.

```bash
uip maestro flow edge add CalcConfigFlow.flow start loadConfiguration1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow loadConfiguration1 readNumbers1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow readNumbers1 whichCalculator1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow whichCalculator1 add1 --source-port case-add
```

```bash
uip maestro flow edge add CalcConfigFlow.flow whichCalculator1 subtract1 --source-port case-subtract
```

```bash
uip maestro flow edge add CalcConfigFlow.flow whichCalculator1 multiply1 --source-port case-multiply
```

```bash
uip maestro flow edge add CalcConfigFlow.flow whichCalculator1 divide1 --source-port case-divide
```

```bash
uip maestro flow edge add CalcConfigFlow.flow add1 csvReportOn1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow subtract1 csvReportOn1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow multiply1 csvReportOn1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow divide1 csvReportOn1
```

```bash
uip maestro flow edge add CalcConfigFlow.flow csvReportOn1 writeReport1 --source-port true
```

```bash
uip maestro flow edge add CalcConfigFlow.flow csvReportOn1 end1 --source-port false
```

```bash
uip maestro flow edge add CalcConfigFlow.flow writeReport1 end1
```

**7f. The variable updates (a hand edit).** Each calculator writes its whole output into
`calculation` when it finishes. There is no CLI command for variable updates, so `jq` writes them.
The `expression` is an object, not an `=js:` string:

```json
"variableUpdates": {
  "add1": [{ "variableId": "calculation", "expression": { "type": "jsExpression", "expression": "$vars.add1.output", "fieldType": "object" } }]
}
```

…and the same for `subtract1`, `multiply1` and `divide1`.

```bash
jq '.variables.variableUpdates = (["add1", "subtract1", "multiply1", "divide1"] | map({key: ., value: [{variableId: "calculation", expression: {type: "jsExpression", expression: ("$vars." + . + ".output"), fieldType: "object"}}]}) | from_entries)' CalcConfigFlow.flow > CalcConfigFlow.flow.tmp
```

```bash
mv CalcConfigFlow.flow.tmp CalcConfigFlow.flow
```

**7g. Map the End node's outputs (a hand edit).** Only `calculation` knows which calculator ran;
`report_path` comes from Load configuration (`""` when the report is off), so it's right on both
branches of the Decision. The `inout` global is mapped too, or `validate` warns about it.

```json
"outputs": {
  "calculation": { "source": "=js:$vars.calculation", "type": "object" },
  "provider_id": { "source": "=js:$vars.calculation.provider_id", "type": "string" },
  "alert_count": { "source": "=js:$vars.calculation.alert_count", "type": "number" },
  "report_path": { "source": "=js:$vars.loadConfiguration1.output.report_path", "type": "string" },
  "overridden_keys": { "source": "=js:$vars.loadConfiguration1.output.overridden_keys", "type": "array" }
}
```

```bash
jq '(.nodes[] | select(.id == "end1")) |= (.outputs = {"calculation": {"source": "=js:$vars.calculation", "type": "object"}, "provider_id": {"source": "=js:$vars.calculation.provider_id", "type": "string"}, "alert_count": {"source": "=js:$vars.calculation.alert_count", "type": "number"}, "report_path": {"source": "=js:$vars.loadConfiguration1.output.report_path", "type": "string"}, "overridden_keys": {"source": "=js:$vars.loadConfiguration1.output.overridden_keys", "type": "array"}})' CalcConfigFlow.flow > CalcConfigFlow.flow.tmp
```

```bash
mv CalcConfigFlow.flow.tmp CalcConfigFlow.flow
```

**7h. Check, tidy, check again.**

```bash
uip maestro flow validate CalcConfigFlow.flow
```

```bash
uip maestro flow format CalcConfigFlow.flow
```

```bash
uip maestro flow validate CalcConfigFlow.flow
```

**Check:** `"Status": "Valid"` both times, with no `Warnings`. Without 7g you'd see one
`MISSING_OUTPUT_MAPPING` per output and one for `calculation`. `format` lays the nodes out and fills
in `variables.nodes`, which is what makes `$vars.<node>.output` resolve at run time: always run it.
It keeps the variable updates: `jq -c '.variables.variableUpdates | keys' CalcConfigFlow.flow`
still lists the four calculators.

### 8. Resources and pack

```bash
cd ..
```

```bash
uip solution resources refresh
```

**Check:** `"Status": "Synced 0 resources (2 already in solution)…"`. Two warnings, that
`CalcConfigFunction` and `CalcConfigFlow` "were not checked for resource contributions", are
expected with this CLI: `refresh` doesn't read these projects' bindings, and step 6 already
declared both resources.

```bash
uip solution resources list --source local
```

**Check:** the asset `CalcApiKey` (type `credentialAsset`), the bucket `CalcConfigFiles`, two
packages and two processes, all in `solution_folder`.

```bash
uip solution pack . --dry-run
```

**Check:** `"Status": "Valid"`. This builds both projects the way a deploy would, without writing a
package.

## What you end up with

```
config-simulation/
├── data/numbers.csv, data/configuration_payload.json   ← the input and the saved values (yours; not packed)
└── CalcConfig/                                          the Solution
    ├── CalcConfig.uipx                                  the two projects            (tool-managed)
    ├── resources/solution_folder/                       asset, bucket, packages, processes (tool-managed)
    ├── AGENTS.md, CLAUDE.md                             uip's notes for AI agents   (generated)
    ├── CalcConfigFlow/CalcConfigFlow.flow               ← the Flow (the source)
    └── CalcConfigFunction/
        ├── configuration.json, settings.py, calculator.py, main.py, test_main.py   (yours)
        ├── bindings.json                                ← the two resources are yours; the rest generated
        └── entry-points.json, main.mermaid, project.uiproj, uv.lock, .env, .agent/,
            .claude/, AGENTS.md, CLAUDE.md, .uipath/, .venv/                        (generated)
```

There is no `.bpmn`: `uip` generates it from the `.flow` when it packs. The Flow folder also has
`operate.json` and `project.uiproj` (generated).

**Jobs per run: 4 or 5**: Load configuration, Read numbers, one calculator, and Write report when the
report is on. The Switch and the Decision run inside the Flow, not as jobs.

## Expected result

**With the saved payload** (`DIVIDE`, `SKIP_ROW`): `provider_id` `DIVIDE`, `alert_count` 1,
`report_path` `output/<year>/<month>/calculation-report.csv` (the run's UTC month),
`overridden_keys` `[]`. The report:

```csv
id,a,b,result,alert,note
N-01,250,2,125,yes,
N-02,12,9,1.33,no,
N-03,-7.5,2.5,-3,no,
N-04,2.01,2,1.01,no,
N-05,42,0,,no,skipped: division by zero
N-06,1,3,0.33,no,
N-07,50,2,25,no,
```

**Each calculator** on `data/numbers.csv` (rows N-01 to N-07; `ROUND_TO` 2, `alert_above` 100):

| `PROVIDER_ID` | Results | `alert_count` |
|---|---|---|
| `ADD` | 252, 21, -5, 4.01, 42, 4, 52 | 1 |
| `SUBTRACT` | 248, 3, -10, 0.01, 42, -2, 48 | 1 |
| `MULTIPLY` | 500, 108, -18.75, 4.02, 0, 3, 100 | 2 (100 is not above 100) |
| `DIVIDE` | 125, 1.33, -3, 1.01, —, 0.33, 25 | 1 |

The tests assert the same numbers.

## Run it

[HOW_TO_RUN.md](HOW_TO_RUN.md) runs this simulation in four levels: the tests, a local run, the
tenant run, and a deployed run started over HTTP with curl or Postman. It also says where to look in the browser, and lists the things only the tenant run can
confirm.

## Try this

1. **A typo in the saved file.** Upload a payload with `"PROVIDER_ID": "DIVDE"`, debug, and read the
   cause (the `jq -r` line in [tenant step 2](HOW_TO_RUN.md#3-on-the-tenant)). Load configuration fails and lists the four allowed values. Upload
   `../data/configuration_payload.json` again to put it back.
2. **Division by zero, the strict way.** Debug with
   `--inputs '{"overrides": {"provider": {"DIVIDE_ON_ZERO": "FAIL"}}, "numbers": []}'`. Divide fails
   on `N-05`. With `ZERO`, N-05's result is 0.
3. **A missing asset.** Debug with
   `--inputs '{"overrides": {"provider": {"API_KEY_ASSET": "NoSuchAsset"}}, "numbers": []}'`. The
   calculator fails, naming the asset; Load configuration and Read numbers still succeed.
4. **Change the configuration without a redeploy.** Change `alert_above` to 10 in a copy of the
   payload, upload it over the old one and debug: `alert_count` changes, and no package changed.
5. **A fifth calculator, `POWER`.** List what has to change, then do it:
   - the form's `PROVIDER_ID` values;
   - `OPERATORS` in `calculator.py` and `OPERATIONS` in `main.py`;
   - a Switch case, a node, two edges and a variable update in the Flow;
   - `EXPECTED` and `ALERTS` in the tests, and this README.

   That list is the cost of one more provider in Evelyn's port, at toy size.

## What building it taught

| Finding | Evidence | What was done |
|---|---|---|
| A Switch is `core.logic.switch` with `cases` (`id`, `label`, `expression`); each case is a port `case-<id>`. `node add` takes the cases in `--input` | `uip maestro flow node add … core.logic.switch --input '{"cases": …}'`, then `validate` Valid | Built **Which calculator?** by command |
| A Switch's or Decision's `matchedCase` output is never set at run time, so a later node can't tell which branch ran by asking it | UiPath's Maestro Flow skill, `decision/impl.md` § Outputs | Each calculator writes the `inout` global `calculation` (7f) |
| Branches of one Switch join by pointing at the same node. A Merge node waits for every input and would hang | The skill's `merge/planning.md` | All four calculators point at **CSV report on?** |
| Variable updates have no CLI command, and their `expression` is an object | The skill's `variables-and-expressions.md`; `uip maestro flow variable --help` lists only add, list, remove | A `jq` edit (7f). `format` keeps it |
| An `inout` global must be mapped on the End node, like an output | `validate` warns `MISSING_OUTPUT_MAPPING` for `calculation` until 7g | Mapped it |
| `projects add` ignores a binding's `"SubType": "credentialAsset"` and makes a Text asset | `find resources` showed `asset/stringAsset/CalcApiKey.json` | Declare the asset first (step 6) |
| `resources add --type Credential` is accepted and makes a Text asset; `--type credentialAsset` makes a Credential | Both tried; only the second gave `"type": "Credential"` | Step 6 uses `credentialAsset` |
| `resources refresh` doesn't read a function's or a Flow's bindings with this CLI | Its two warnings: "was not checked for resource contributions" | Resources come from step 6 |
| A file next to the code ships in the function's package: `configuration.json`, and also `.env` | A real `uip solution pack`, unzipped: `content/configuration.json`, `content/.env` | The form lives in the function folder; never run `uipath auth` there |
| `uipath init` turns `config: dict` into `{"type": "object", "additionalProperties": true}` | `entry-points.json` | `config` passes as one object |
| `round()` rounds the binary value, so 2.01 / 2 gives 1.0 | `round(2.01 / 2, 2)` | `Decimal(str(...))`, half up; N-04 guards it |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Fewer than `32 passed` | A file changed, or `data/` was edited | Read the failing test's name; restore `data/` from this folder |
| `Unknown setting '…'` or `… allowed: …` | A typo in the payload or the overrides | Fix the key or value the message names |
| Load configuration fails: file not found | The payload isn't in the bucket yet | [Tenant step 3](HOW_TO_RUN.md#3-on-the-tenant) |
| `Couldn't read the Credential asset 'CalcApiKey'` | The asset isn't in the run's folder | [Tenant step 4](HOW_TO_RUN.md#3-on-the-tenant), the `assets create` line |
| `The Credential asset 'CalcApiKey' has no password` | The asset has no value | [Tenant step 4](HOW_TO_RUN.md#3-on-the-tenant) |
| `This node calculates ADD, but configuration.PROVIDER_ID is …` | A Switch case points at the wrong node | Check 7e's `case-…` edges |
| `[400001] No condition for an outgoing flow was met` | `provider_id` reached the Switch empty | Read Load configuration's output in the instance view |
| `N-05: division by zero` | `DIVIDE_ON_ZERO` is `FAIL` | Set it to `SKIP_ROW` or `ZERO` |
| `find resources` shows `asset/stringAsset/CalcApiKey.json` | `projects add` ran before the asset was declared | `uip solution resources remove <its key>`, then step 6's `resources add` |
| `validate`: `MISSING_OUTPUT_MAPPING` | 7g not done | Do it |
| `echo $FN` prints nothing | New terminal, or the function isn't in the Solution | Re-run step 6, then 7b |
| Node IDs end in `2` | A node added twice | Start again from step 1 in an empty folder |

## Done when

- [ ] `uv run pytest -q` passes (32).
- [ ] The local run (step 5) prints the report in [Expected result](#expected-result), and the typo
  fails with the allowed values.
- [ ] The Flow `validate`s as Valid with no warnings, and `uip solution pack . --dry-run` is Valid.
- [ ] You can say where each of the three layers lives, which one wins, and why the API key is in an
  asset and not in the payload.
- [ ] **[On the tenant](HOW_TO_RUN.md#3-on-the-tenant):**
  - runs A, B and C return what their checks say;
  - the report in the bucket matches [Expected result](#expected-result);
  - you've noted which rows of [Things only the tenant run can confirm](HOW_TO_RUN.md#things-only-the-tenant-run-can-confirm) turned out true.
