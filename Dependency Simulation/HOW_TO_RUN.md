# How to run the Dependency Simulation

[README.md](README.md) explains what this simulates and builds it from an empty folder. This file
runs what's already here, in four levels. The first two need no tenant and take a minute.

| Level | Needs | Takes | Shows |
|---|---|---|---|
| [1. Tests](#1-tests) | `uv` | 1 minute | The library's rules, the Java division trap included, and that the function uses the library from the shipped wheel |
| [2. A local run](#2-a-local-run) | `uv`; `uip` for the last part | 2 minutes | Each row through the library, the dependency in `uv tree`, and the wheel inside the function's package |
| [3. On the tenant](#3-on-the-tenant) | `uip` logged in, a tenant | 10–20 minutes | Whether the tenant installs the library from the wheel: `library_version` comes back `1.0.0` |
| [4. Deployed, over HTTP](#4-deployed-and-started-over-http) | `uip` logged in, a tenant, a personal access token, `curl` or Postman | 30 minutes | The Solution deployed to its own folder, and the Flow started by an HTTP call, as another system would |

**Status:** levels 1 and 2 were run as written on a fresh copy on 2026-10-16, and every check
passed. Levels 3 and 4 haven't been run on a tenant yet.

## 0. Get it

```bash
git clone https://github.com/kowshik-narayanam/evelyn-simulations.git
```

```bash
cd "evelyn-simulations/Dependency Simulation"
```

The tools are listed in the repo's [README](../README.md#what-you-need). There is nothing to
install by hand: the first `uv run` in a project creates its `.venv` with Python 3.11 and the pinned
packages, the function's `evsim-calc` included, from `wheels/`.

## 1. Tests

The library first, in its own project:

```bash
cd evsim-calc
```

```bash
uv run pytest -q
```

**Check:** `18 passed`. Then the function, which uses the library as a dependency:

```bash
cd ../DependencySim/DependencySimFunction
```

```bash
uv run pytest -q
```

**Check:** `10 passed`. Two of them test the dependency itself: `evsim_calc` is imported from the
function's `.venv`, installed from `wheels/`, and `uv.lock`'s sha256 matches the wheel there.

## 2. A local run

You're in `DependencySim/DependencySimFunction`. The dependency, as `uv` sees it:

```bash
uv tree --depth 1
```

**Check:** `evsim-calc v1.0.0` among the function's dependencies, next to `pydantic` and `uipath`.

**Each row through the library.** The function needs the tenant's bucket, so locally you call the
parser and the library directly, the same calls `main` makes:

```bash
uv run python -c "import pathlib, evsim_calc, calculations; [print(r.integer_1, r.operand, r.integer_2, '=', evsim_calc.calculate(r.integer_1, r.integer_2, r.operand)) for r in calculations.parse_calculations(pathlib.Path('../../data/calculations.csv').read_text())]; print('evsim-calc', evsim_calc.__version__)"
```

**Check:** ten lines, from `12 add 30 = 42` to `0 divide 5 = 0`, with `-7 divide 2 = -3`, then
`evsim-calc 1.0.0`. The trap the library avoids:

```bash
uv run python -c "print(-7 // 2, int(-7 / 2))"
```

**Check:** `-4 -3`. Python's `//` rounds down; Java, and `evsim-calc`, truncate toward zero.

**The wheel inside the package.** This part needs `uip` logged in; it reads from the tenant and
changes nothing. Pack the Solution to a folder outside it:

```bash
cd ..
```

```bash
uip solution pack . /tmp/dependency-pack --output json
```

```bash
unzip -q -o /tmp/dependency-pack/DependencySim_1.0.0.zip -d /tmp/dependency-pack/unzipped
```

```bash
unzip -l /tmp/dependency-pack/unzipped/files/*/DependencySim.Function.DependencySimFunction.1.0.0.nupkg | grep -E "wheels|uv.lock|pyproject"
```

**Check:** `content/pyproject.toml`, `content/uv.lock` and
`content/wheels/evsim_calc-1.0.0-py3-none-any.whl`. That package is what the tenant gets.

Go back to the simulation folder for level 3:

```bash
cd ..
```

## 3. On the tenant

**Needs a tenant login; not run yet.** These steps create a bucket on the tenant you're logged
into, upload a file to it and run two jobs. Use a tenant you're allowed to experiment on.

Every run is a `uip maestro flow debug <Flow>`, from the Solution folder. It does three things:
- **packs** the Solution in that folder: the function project, with its `wheels/`, and the Flow;
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
cd DependencySim
```

```bash
uip solution resources refresh
```

2. **First debug run: it should fail at Calculate.** The run creates the bucket, empty
   (**Inference**, as in the other simulations), so there is no CSV to read yet. It is also the
   first test of the dependency: the job installs the function's dependencies before `main` runs
   (**Inference**). A "file not found" error means the library installed; an error that names
   `evsim-calc` means it didn't (see
   [Things only the tenant run can confirm](#things-only-the-tenant-run-can-confirm)).

```bash
uip maestro flow debug DependencySimFlow --inputs '{"csv_path": "input/calculations.csv"}' --output json > /tmp/dependency-debug-1.json
```

```bash
jq '.Data.finalStatus' /tmp/dependency-debug-1.json
```

```bash
jq -r '.Data.variables.elements[] | select(.outputs.Error) | "\(.elementId) \(.outputs.Error.detail)"' /tmp/dependency-debug-1.json
```

**Check:** `Faulted`, and the cause names `input/calculations.csv`.

3. **Upload the CSV.** Look up your personal workspace and the bucket's key:

```bash
WORKSPACE=$(uip or folders list --limit 100 --output plain --output-filter "[?Type=='Personal'].Path | [0]")
```

```bash
BUCKET_KEY=$(uip or buckets list --folder-path "$WORKSPACE" --limit 100 --output plain --output-filter "[?Name=='DependencySimFiles'].Key | [0]")
```

```bash
echo "$WORKSPACE | $BUCKET_KEY"
```

**Check:** your workspace's name (`<your email>'s workspace`) and a GUID. If the GUID is missing,
the debug run didn't create the bucket in your workspace. Create it, then run the `BUCKET_KEY=` line
again:

```bash
uip or buckets create DependencySimFiles --folder-path "$WORKSPACE"
```

```bash
uip or bucket-files upload "$BUCKET_KEY" input/calculations.csv --folder-path "$WORKSPACE" --file ../data/calculations.csv --content-type text/csv
```

4. **Second debug run: the real one.**

```bash
uip maestro flow debug DependencySimFlow --inputs '{"csv_path": "input/calculations.csv"}' --output json > /tmp/dependency-debug-2.json
```

```bash
jq '.Data' /tmp/dependency-debug-2.json
```

**Check:**
- `count` 10 and `library_version` `1.0.0`: the tenant ran the library from the shipped wheel;
- `results` as in [Expected result](README.md#expected-result), with `-3` for `-7 divide 2`;
- in Maestro's instance view, **Calculate**'s output holds the same.

- **A new terminal forgets `WORKSPACE` and `BUCKET_KEY`.** Run their lines again.
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
| Where its files are | My Workspace | The new folder, `DependencySim Deployed` |
| What starts it | `uip maestro flow debug` | An HTTP call: curl, Postman, or another system |

Start from the simulation folder.

1. **Pack and publish** the Solution:

```bash
cd DependencySim
```

```bash
uip solution resources refresh
```

```bash
uip solution pack . /tmp/dependency-pack --version 1.0.0 --output json
```

```bash
uip solution publish /tmp/dependency-pack/DependencySim_1.0.0.zip --output json
```

**Check:** `uip solution packages list --name DependencySim --output json` lists version `1.0.0`. To
publish again after a change, pack with a higher `--version`.

2. **Deploy.** This creates the folder `DependencySim Deployed` and, in it, the Flow, the function (with its wheel) and an empty bucket:

```bash
uip solution deploy run -n dependency-sim --package-name DependencySim --package-version 1.0.0 --folder-name "DependencySim Deployed" --output json
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
curl -s --get "$BASE/odata/Folders" --data-urlencode "\$filter=contains(DisplayName,'DependencySim')" --data-urlencode '$select=Id,FullyQualifiedName' -H "Authorization: Bearer $TOKEN" | jq '.value'
```

**Check:** one folder. Copy its two values:

```bash
FOLDER_ID=paste-the-Id
```

```bash
DEPLOY_FOLDER="paste-the-FullyQualifiedName"
```

5. **Put the input in the deployed bucket.** The deployment made its own bucket, new and empty; the
   one in My Workspace from level 3 isn't used.

```bash
DEPLOY_BUCKET=$(uip or buckets list --folder-path "$DEPLOY_FOLDER" --limit 100 --output plain --output-filter "[?Name=='DependencySimFiles'].Key | [0]")
```

```bash
uip or bucket-files upload "$DEPLOY_BUCKET" input/calculations.csv --folder-path "$DEPLOY_FOLDER" --file ../data/calculations.csv --content-type text/csv
```

**Check:** `echo "$DEPLOY_BUCKET"` printed a GUID before the upload.

6. **Find the Flow's release key.** A release is Orchestrator's name for a deployed process, and
   StartJobs asks for its key:

```bash
curl -s --get "$BASE/odata/Releases" --data-urlencode "\$filter=Name eq 'DependencySimFlow'" --data-urlencode '$select=Key,Name' -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq '.value'
```

```bash
RELEASE_KEY=paste-the-Key
```

7. **Start it.** `InputArguments` holds the Flow's `in` variables as a JSON **string**, not an
   object, so `jq` builds the body:

```bash
jq -n --arg k "$RELEASE_KEY" '{startInfo: {ReleaseKey: $k, RunAsMe: true, InputArguments: ({csv_path: "input/calculations.csv"} | tojson)}}' > /tmp/start-job.json
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

**Check:** `count` 10 and `library_version` `1.0.0`, the same as the second debug run in level 3. A deployed job installs the function's dependencies the same way a debug run does (**Inference**), so this checks the wheel again, in a folder of its own.

10. **Remove the deployment** when you're done. This deletes the folder `DependencySim Deployed` and everything
    the deployment made in it, the bucket's files included:

```bash
uip solution deploy uninstall dependency-sim --yes
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
| Find the folder | `GET {{base}}/odata/Folders?$filter=contains(DisplayName,'DependencySim')` | None |
| Find the release | `GET {{base}}/odata/Releases?$filter=Name eq 'DependencySimFlow'` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |
| Start | `POST {{base}}/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs` | The same, plus `Content-Type: application/json` |
| Poll | `GET {{base}}/odata/Jobs({{jobId}})` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |

4. **The Start request's body** (raw, JSON). `InputArguments` is a string, so its quotes are
   escaped:

```json
{"startInfo": {"ReleaseKey": "{{releaseKey}}", "RunAsMe": true, "InputArguments": "{\"csv_path\": \"input/calculations.csv\"}"}}
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
| One run, node by node | The Studio Web link in the debug output, for example `jq -r '.Data.studioWebUrl' /tmp/dependency-debug-2.json`. The canvas opens in Debug mode. The panel at the bottom has **Spans** (one per node) and **Incidents** (the error). Click **Calculate** to see its output in its properties panel ([Debugging basics](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/debugging-effectively)) |
| Every Flow run in the tenant | Maestro → **Flow instances** (Preview) ([docs](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/flow-instances-view)). Whether debug runs show up there is unverified |
| The bucket `DependencySimFiles` and its file | Orchestrator → **My Folders** → **My Workspace** → **Storage Buckets** tab → `DependencySimFiles`. Buckets belong to a folder, so they don't show while **Tenant** is selected. Look for `input/calculations.csv` |
| The function's run and its log | Orchestrator → **My Workspace** → **Automations** → **Jobs**: the `DependencySimFunction` job (**Inference**). Its log should have `evsim-calc 1.0.0 calculated 10 rows from input/calculations.csv`, which `main.py` writes, and may show the dependency install |

The CLI calls your personal workspace `<your email>'s workspace`. The web UI calls the same folder
**My Workspace**.

## Things only the tenant run can confirm

| Unknown | Why it matters | If it's wrong |
|---|---|---|
| Does the job install the function's dependencies from `uv.lock`, so `evsim-calc` comes from `wheels/`? | The whole example. `pip` doesn't read `[tool.uv.sources]`, so an install from `pyproject.toml` alone would look for `evsim-calc==1.0.0` on PyPI | **Calculate** fails before `main` runs, naming `evsim-calc` (for example `No matching distribution found`). Then ship the wheel as a URL dependency, `"evsim-calc @ https://…/evsim_calc-1.0.0-py3-none-any.whl"`, which `pip` and `uv` both read |
| Does the install find `wheels/…` relative to the unpacked package? | Same | An error with `wheels/evsim_calc-1.0.0-py3-none-any.whl` and "not found" |
| Does `library_version` come back as `1.0.0`? | The proof that the shipped wheel is what ran | Another value means the robot found `evsim-calc` somewhere else: note where |
| Does the first debug run create the bucket, and in which folder? | Steps 2–3 | Create it by hand (step 3) and note the folder |
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
