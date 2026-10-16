# How to run the Configuration Simulation

[README.md](README.md) explains what this simulates and builds it from an empty folder. This file
runs what's already here, in four levels. The first two need no tenant and take a minute.

| Level | Needs | Takes | Shows |
|---|---|---|---|
| [1. Tests](#1-tests) | `uv` | 1 minute | The settings and calculator rules hold on the data's traps: rounding, division by zero, a value on the threshold |
| [2. A local run](#2-a-local-run) | `uv` | 1 minute | The report a run writes, from the saved configuration and from an override |
| [3. On the tenant](#3-on-the-tenant) | `uip` logged in, a tenant | 20–40 minutes | The whole Flow: the three layers, the Switch, the Credential asset, the report in the bucket |
| [4. Deployed, over HTTP](#4-deployed-and-started-over-http) | `uip` logged in, a tenant, a personal access token, `curl` or Postman | 30 minutes | The Solution deployed to its own folder, and the Flow started by an HTTP call, as another system would |

**Status:** levels 1 and 2 were run as written on a fresh copy on 2026-10-15, and every check
passed. Levels 3 and 4 haven't been run on a tenant yet.

## 0. Get it

```bash
git clone https://github.com/kowshik-narayanam/evelyn-simulations.git
```

```bash
cd "evelyn-simulations/Configuration Simulation"
```

The tools are listed in the repo's [README](../README.md#what-you-need). There is nothing to
install by hand: the first `uv run` creates the project's `.venv` with Python 3.11 and the pinned
packages (like `mvn` fetching dependencies on the first build).

## 1. Tests

```bash
cd CalcConfig/CalcConfigFunction
```

```bash
uv run pytest -q
```

**Check:** `32 passed`.

## 2. A local run

On the tenant, the function reads a bucket and an asset, which a laptop doesn't have. So a local run
calls the code underneath: the same configuration and calculation that **Load configuration**,
**Read numbers** and **Divide** run. You're still in `CalcConfig/CalcConfigFunction`.

**The saved configuration** (`data/configuration_payload.json`: `DIVIDE`, `SKIP_ROW`):

```bash
uv run python -c "import json, settings, calculator; c = settings.load(json.load(open('../../data/configuration_payload.json')), None); print(calculator.to_csv(calculator.calculate(c['configuration']['PROVIDER_ID'], calculator.parse_numbers(open('../../data/numbers.csv').read()), c)))"
```

**Check:** the report in [Expected result](README.md#expected-result). There are seven rows: N-01 is
`125,yes`, and N-05 is `skipped: division by zero`.

**An override for one run.** The `None` above is the run's `overrides`. Pass one setting instead:

```bash
uv run python -c "import json, settings, calculator; c = settings.load(json.load(open('../../data/configuration_payload.json')), {'configuration': {'PROVIDER_ID': 'MULTIPLY'}}); print(calculator.to_csv(calculator.calculate(c['configuration']['PROVIDER_ID'], calculator.parse_numbers(open('../../data/numbers.csv').read()), c)))"
```

**Check:** N-01 is `500,yes`, and N-07 is `100,no`, because 100 is not above the threshold of 100.
The override beat the saved file, and the file didn't change.

**A typo, which fails on purpose:**

```bash
uv run python -c "import settings; settings.load({'configuration': {'PROVIDER_ID': 'DIVDE'}}, None)"
```

**Check:** the last line is `ValueError: configuration.PROVIDER_ID is 'DIVDE'; allowed: ADD,
SUBTRACT, MULTIPLY, DIVIDE`. A tenant run shows the same message at **Load configuration**.

Go back to the simulation folder for level 3:

```bash
cd ../..
```

## 3. On the tenant

**Needs a tenant login; not run yet.** These steps create a bucket and a Credential asset on the
tenant you're logged into, upload two files, set the asset's value and run up to fifteen jobs.
Use a tenant you're allowed to experiment on.

Every run is a `uip maestro flow debug <Flow>`, from the Solution folder. It does three things:
- **packs** the Solution in that folder: the function projects and the Flows;
- **uploads** it to Studio Web, replacing the Studio Web solution with the same ID, so edits you
  made there are lost;
- **runs** the Flow once with the `--inputs` you give it. It waits, 1 to 5 minutes, and prints JSON
  only at the end.

The steps:

1. Check the login and, from this folder, go to the Solution:

```bash
uip login status
```

```bash
cd CalcConfig
```

```bash
uip solution resources refresh
```

2. **First debug run: it should fail at Load configuration.** The run creates the bucket, empty, and
   the asset, without a value (**Inference**, as in CsvProcessor Simulation). There is no saved
   payload in the bucket yet: "a missing file fails the run" at work.

```bash
uip maestro flow debug CalcConfigFlow --inputs '{"overrides": {}, "numbers": []}' --output json > /tmp/calc-debug-0.json
```

It takes 1 to 5 minutes and prints only at the end.

```bash
jq '.Data.finalStatus' /tmp/calc-debug-0.json
```

```bash
jq -r '.Data.variables.elements[] | select(.outputs.Error) | "\(.elementId) \(.outputs.Error.detail)"' /tmp/calc-debug-0.json
```

**Check:** `Faulted`, and the cause names `config/configuration_payload.json`.

3. **Upload the saved payload and the numbers.** Look up your personal workspace and the bucket's key:

```bash
WORKSPACE=$(uip or folders list --limit 100 --output plain --output-filter "[?Type=='Personal'].Path | [0]")
```

```bash
BUCKET_KEY=$(uip or buckets list --folder-path "$WORKSPACE" --limit 100 --output plain --output-filter "[?Name=='CalcConfigFiles'].Key | [0]")
```

```bash
echo "$WORKSPACE | $BUCKET_KEY"
```

**Check:** your workspace's name (`<your email>'s workspace`) and a GUID. If the GUID is missing,
the debug run didn't create the bucket in your workspace. Create it, then run the `BUCKET_KEY=` line
again:

```bash
uip or buckets create CalcConfigFiles --folder-path "$WORKSPACE"
```

```bash
uip or bucket-files upload "$BUCKET_KEY" config/configuration_payload.json --folder-path "$WORKSPACE" --file ../data/configuration_payload.json --content-type application/json
```

```bash
uip or bucket-files upload "$BUCKET_KEY" input/numbers.csv --folder-path "$WORKSPACE" --file ../data/numbers.csv --content-type text/csv
```

4. **Give the Credential asset a value.** The calculators only check that a password is there; use a
   made-up one. Never put a real key in a command: it stays in your shell history.

```bash
ASSET_KEY=$(uip or assets list --folder-path "$WORKSPACE" --name CalcApiKey --output plain --output-filter "[?Name=='CalcApiKey'].Key | [0]")
```

```bash
echo "$ASSET_KEY"
```

**Check:** a GUID. Then set the value, in `username:password` form:

```bash
uip or assets update "$ASSET_KEY" "calc-user:not-a-real-key" --folder-path "$WORKSPACE"
```

Or in the browser: Orchestrator → your workspace folder → **Assets** → `CalcApiKey` → edit, and
type a username and password. If `ASSET_KEY` is empty, the debug run didn't create the asset;
create it, then go on:

```bash
uip or assets create CalcApiKey "calc-user:not-a-real-key" --type Credential --folder-path "$WORKSPACE"
```

5. **Run A: the saved payload.**

```bash
uip maestro flow debug CalcConfigFlow --inputs '{"overrides": {}, "numbers": []}' --output json > /tmp/calc-debug-a.json
```

```bash
jq '.Data' /tmp/calc-debug-a.json
```

**Check:** `provider_id` `DIVIDE`, `alert_count` 1, a `report_path`. In Maestro's instance view, the
Switch took `DIVIDE` and only **Divide** ran; open **Load configuration** to see the configuration
this run used. Then read the report (same UTC month as the run):

```bash
uip or bucket-files download "$BUCKET_KEY" "output/$(date -u +%Y/%m)/calculation-report.csv" --folder-path "$WORKSPACE"
```

**Check:** the report in [Expected result](README.md#expected-result).

6. **Run B: another calculator, no report.** Overrides change two settings for this run only:

```bash
uip maestro flow debug CalcConfigFlow --inputs '{"overrides": {"configuration": {"PROVIDER_ID": "MULTIPLY", "reports": {"csv": {"enable": false}}}}, "numbers": []}' --output json > /tmp/calc-debug-b.json
```

```bash
jq '.Data' /tmp/calc-debug-b.json
```

**Check:** `provider_id` `MULTIPLY`, `alert_count` 2, `report_path` `""`, and `overridden_keys` lists
both settings. The Decision took `false`, so **Write report** never ran. The saved payload in the
bucket is unchanged: overrides never write back.

7. **Run C: API input.** The numbers come with the run instead of from the bucket:

```bash
uip maestro flow debug CalcConfigFlow --inputs '{"overrides": {"configuration": {"INPUT_TYPE": "API", "PROVIDER_ID": "ADD"}}, "numbers": [{"id": "R-1", "a": 99, "b": 2}, {"id": "R-2", "a": 1, "b": 1}]}' --output json > /tmp/calc-debug-c.json
```

```bash
jq '.Data' /tmp/calc-debug-c.json
```

**Check:** `provider_id` `ADD`, `alert_count` 1 (99 + 2 = 101).

- **A new terminal forgets `WORKSPACE`, `BUCKET_KEY` and `ASSET_KEY`.** Run their lines again.
- **Don't run `uipath auth` in the function folder.** `uip solution pack`, which `flow debug` also
  uses, ships `.env` inside the package. `uip login` keeps its login in `~/.uipath/`.
- **Run either this folder or your rebuild on the tenant, not both.** They use the same names, and
  Orchestrator binds by name.

## 4. Deployed, and started over HTTP

**Untested.** Nobody has run this level yet. It's written from the `uip` CLI's help and source and
from the Orchestrator API docs. It deploys the Solution into an Orchestrator folder of its own, then
starts the Flow the way an outside system would: with an HTTP call. That's the UiPath form of
starting a WorkFusion BP through its REST API.

| | Level 3 | Level 4 |
|---|---|---|
| What runs | A copy uploaded to Studio Web | A published package, deployed to a folder |
| Where its files are | My Workspace | The new folder, `CalcConfig Deployed` |
| What starts it | `uip maestro flow debug` | An HTTP call: curl, Postman, or another system |

Start from the simulation folder.

1. **Pack and publish** the Solution:

```bash
cd CalcConfig
```

```bash
uip solution resources refresh
```

```bash
uip solution pack . /tmp/calc-pack --version 1.0.0 --output json
```

```bash
uip solution publish /tmp/calc-pack/CalcConfig_1.0.0.zip --output json
```

**Check:** `uip solution packages list --name CalcConfig --output json` lists version `1.0.0`. To
publish again after a change, pack with a higher `--version`.

2. **Deploy.** This creates the folder `CalcConfig Deployed` and, in it, the Flow, the function, an empty bucket and the Credential asset without a value:

```bash
uip solution deploy run -n calc-config --package-name CalcConfig --package-version 1.0.0 --folder-name "CalcConfig Deployed" --output json
```

**Check:** `Status` is `DeploymentSucceeded`, and `ActivationStatus` is `SuccessfulActivate`. If
the folder name is taken, the deploy picks another; step 4 finds it either way.

3. **A token for the HTTP calls.** In UiPath, select your user icon → **Preferences** → **Personal
   access token** → **Generate new token**. Under **Scopes**, pick from **Orchestrator**: `OR.Jobs`
   (start and read jobs), `OR.Execution` (find the process) and `OR.Folders.Read` (find the
   folder; **Inference** on this one's name). Copy it; it's shown once. Then read it into the shell
   without echoing it, so it stays out of your history and your files:

```bash
read -s TOKEN
```

Paste the token and press Enter; nothing shows. Then set the API's base URL. Replace `<org>` and
`<tenant>` with the first two parts of the path in your Orchestrator URL:

```bash
BASE="https://cloud.uipath.com/<org>/<tenant>/orchestrator_"
```

4. **Find the folder.** Every later call names it by its numeric `Id`:

```bash
curl -s --get "$BASE/odata/Folders" --data-urlencode "\$filter=contains(DisplayName,'CalcConfig')" --data-urlencode '$select=Id,FullyQualifiedName' -H "Authorization: Bearer $TOKEN" | jq '.value'
```

**Check:** one folder. Copy its two values:

```bash
FOLDER_ID=paste-the-Id
```

```bash
DEPLOY_FOLDER="paste-the-FullyQualifiedName"
```

5. **Fill the deployed folder.** The deployment made its own bucket and asset; the ones in My
   Workspace from level 3 aren't used. Upload the saved configuration and the numbers:

```bash
DEPLOY_BUCKET=$(uip or buckets list --folder-path "$DEPLOY_FOLDER" --limit 100 --output plain --output-filter "[?Name=='CalcConfigFiles'].Key | [0]")
```

```bash
uip or bucket-files upload "$DEPLOY_BUCKET" config/configuration_payload.json --folder-path "$DEPLOY_FOLDER" --file ../data/configuration_payload.json --content-type application/json
```

```bash
uip or bucket-files upload "$DEPLOY_BUCKET" input/numbers.csv --folder-path "$DEPLOY_FOLDER" --file ../data/numbers.csv --content-type text/csv
```

Then give the asset a made-up value:

```bash
DEPLOY_ASSET=$(uip or assets list --folder-path "$DEPLOY_FOLDER" --name CalcApiKey --output plain --output-filter "[?Name=='CalcApiKey'].Key | [0]")
```

```bash
uip or assets update "$DEPLOY_ASSET" "calc-user:not-a-real-key" --folder-path "$DEPLOY_FOLDER"
```

**Check:** `echo "$DEPLOY_BUCKET | $DEPLOY_ASSET"` prints two GUIDs.

6. **Find the Flow's release key.** A release is Orchestrator's name for a deployed process, and
   StartJobs asks for its key:

```bash
curl -s --get "$BASE/odata/Releases" --data-urlencode "\$filter=Name eq 'CalcConfigFlow'" --data-urlencode '$select=Key,Name' -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq '.value'
```

```bash
RELEASE_KEY=paste-the-Key
```

7. **Start it.** `InputArguments` holds the Flow's `in` variables as a JSON **string**, not an
   object, so `jq` builds the body:

```bash
jq -n --arg k "$RELEASE_KEY" '{startInfo: {ReleaseKey: $k, RunAsMe: true, InputArguments: ({overrides: {}, numbers: []} | tojson)}}' > /tmp/start-job.json
```

```bash
curl -s -X POST "$BASE/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" -H "Content-Type: application/json" -d @/tmp/start-job.json | jq '.value[0] | {Id, Key, State}'
```

**Check:** a job `Id`, with `State` `Pending` or `Running`. `RunAsMe: true` is what
`uip maestro flow process run` sends too.

```bash
JOB_ID=paste-the-Id
```

8. **Poll until it ends**, every 10 seconds for up to 10 minutes:

```bash
for i in $(seq 60); do STATE=$(curl -s "$BASE/odata/Jobs($JOB_ID)" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq -r .State); echo "$STATE"; case "$STATE" in Successful|Faulted|Stopped) break;; esac; sleep 10; done
```

**Check:** it ends with `Successful`. When a node faults, a Flow's job can stay `Running` instead
of turning `Faulted`. If it's still `Running` after 5 minutes, open the run in Maestro → **Flow
instances** and read its incident.

9. **Read the result.** `OutputArguments` is a JSON string too:

```bash
curl -s "$BASE/odata/Jobs($JOB_ID)" -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq '.OutputArguments | fromjson?'
```

**Check:** `provider_id` `DIVIDE` and `alert_count` 1, the same as run A in level 3. For run B or C, put their `--inputs` object in the `jq -n` line of step 7 and start again.

Then the report, from the deployed bucket (same UTC month as the run):

```bash
uip or bucket-files download "$DEPLOY_BUCKET" "output/$(date -u +%Y/%m)/calculation-report.csv" --folder-path "$DEPLOY_FOLDER"
```

**Check:** the report in [Expected result](README.md#expected-result).

10. **Remove the deployment** when you're done. This deletes the folder `CalcConfig Deployed` and everything
    the deployment made in it, the bucket's files included:

```bash
uip solution deploy uninstall calc-config --yes
```

### The same calls in Postman

1. **An environment** with five variables: `base` (the `BASE` above), `folderId`, `releaseKey`,
   `jobId`, and `token` with type **secret**. Put the token in **Current value** only: Postman
   syncs initial values to its cloud, and current values stay on your machine.
2. **A collection** whose **Authorization** tab is **Bearer Token** with `{{token}}`. Each
   request in it inherits that.
3. **Four requests:**

| Request | Method and URL | Extra headers |
|---|---|---|
| Find the folder | `GET {{base}}/odata/Folders?$filter=contains(DisplayName,'CalcConfig')` | None |
| Find the release | `GET {{base}}/odata/Releases?$filter=Name eq 'CalcConfigFlow'` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |
| Start | `POST {{base}}/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs` | The same, plus `Content-Type: application/json` |
| Poll | `GET {{base}}/odata/Jobs({{jobId}})` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |

4. **The Start request's body** (raw, JSON). `InputArguments` is a string, so its quotes are
   escaped:

```json
{"startInfo": {"ReleaseKey": "{{releaseKey}}", "RunAsMe": true, "InputArguments": "{\"overrides\": {}, \"numbers\": []}"}}
```

5. **Save the job's Id** for the Poll request: in the Start request's **Scripts** →
   **Post-response** (called **Tests** in older Postman versions), add:

```js
pm.environment.set("jobId", pm.response.json().value[0].Id);
```

Don't export or share the environment: it holds your token.

## Where to look in the browser

| To see | Go to |
|---|---|
| One run, node by node | The Studio Web link in the debug output, for example `jq -r '.Data.studioWebUrl' /tmp/calc-debug-a.json`. The canvas opens in Debug mode. The panel at the bottom has **Spans** (one per node) and **Incidents** (the error). Click a node to see its output in its properties panel ([Debugging basics](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/debugging-effectively)). The Switch shows which case it took |
| Every Flow run in the tenant | Maestro → **Flow instances** (Preview) ([docs](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/flow-instances-view)). Whether debug runs show up there is unverified |
| The bucket `CalcConfigFiles` and its files | Orchestrator → **My Folders** → **My Workspace** → **Storage Buckets** tab → `CalcConfigFiles`. Buckets belong to a folder, so they don't show while **Tenant** is selected. Look for `config/`, `input/` and, after run A, `output/<year>/<month>/` |
| The Credential asset `CalcApiKey` | Orchestrator → **My Workspace** → **Assets** → `CalcApiKey`. Edit it there to set or change its value |
| Each function's run | Orchestrator → **My Workspace** → **Automations** → **Jobs**: one job per function node (**Inference**) |

The CLI calls your personal workspace `<your email>'s workspace`. The web UI calls the same folder
**My Workspace**.

## Things only the tenant run can confirm

| Unknown | Why it matters | If it's wrong |
|---|---|---|
| Does the first debug run create the bucket and the Credential asset, and in which folder? | Steps 2–4 | Create them by hand (steps 3 and 4) |
| Does a later debug run keep the asset's value, or reset it? | Runs A–C | The calculator fails with `has no password`: set it again, and note it |
| Does `retrieve_credential` find the asset in the run's folder without a `folder_path`? | Every calculator | `Couldn't read the Credential asset 'CalcApiKey'`: look at the asset's folder |
| Do the Switch's case expressions see `provider_id` as text? | The whole Flow | `[400001] No condition for an outgoing flow was met`: read Load configuration's output |
| Does `calculation` hold the calculator's output by the time the Decision runs? | Write report and End | Write report writes a header only, and End's `alert_count` is empty: read the instance view |
| Does `config` pass between nodes unchanged? It is checked again in each node | Every node after Load configuration | `Unknown setting …` naming a key Maestro added |
| Does the deploy accept the Credential asset without a value? | Level 4, step 2 | The deploy or its activation names `CalcApiKey`. Fetch the deploy configuration (`uip solution deploy config get CalcConfig -d /tmp/calc-config.json`), give the asset a value there or link it to the one in My Workspace (`uip solution deploy config link`), and deploy with `--config-file /tmp/calc-config.json` |
| Does `deploy run` without `--parent-folder-path` make a top-level folder you can use? | Level 4, step 2 | Deploy under a folder you can create in: add `--parent-folder-path Shared` |
| Can a job start in the new folder? It inherits no members | Level 4, step 7 | An error about robots or permissions: in the browser, open the folder's settings and add your user to it |
| Does `RunAsMe: true` work with a personal access token? | Level 4, step 7 | StartJobs refuses it: remove `RunAsMe` from the body |
| Does a Flow job's `OutputArguments` hold the End node's outputs? | Level 4, step 9 | It's empty: read the outputs in Maestro → Flow instances |

## When a run fails

1. Open the Studio Web link (`jq -r '.Data.studioWebUrl' <the debug json>`), then **Incidents**. It
   names the node and the error.
2. Look up the error in [Troubleshooting](README.md#troubleshooting).
3. Check [Things only the tenant run can confirm](#things-only-the-tenant-run-can-confirm). Those are
   the open questions: nobody has run this on a tenant yet. Whatever you find there, the table
   should record it. Update the row, and drop the **Inference** label once it's confirmed.
