# How to run the CsvProcessor Simulation

[README.md](README.md) explains what this simulates and builds it from an empty folder. This file
runs what's already here, in four levels. The first two need no tenant and take a minute.

| Level | Needs | Takes | Shows |
|---|---|---|---|
| [1. Tests](#1-tests) | `uv` | 1 minute | The CSV parser, the sort-and-split rule, and that the two contract copies match |
| [2. A local run](#2-a-local-run) | `uv` | 1 minute | The two sections, by handing one function's output to the other, as the Flows do |
| [3. On the tenant](#3-on-the-tenant) | `uip` logged in, a tenant | 10–20 minutes | Both Flows: the parent calling the child, and the two CSVs in the bucket |
| [4. Deployed, over HTTP](#4-deployed-and-started-over-http) | `uip` logged in, a tenant, a personal access token, `curl` or Postman | 30 minutes | The Solution deployed to its own folder, and the parent Flow started by an HTTP call, as another system would |

**Status:** levels 1 and 2 were run as written on a fresh copy on 2026-10-15, and every check
passed. Levels 3 and 4 haven't been run on a tenant yet.

## 0. Get it

```bash
git clone https://github.com/kowshik-narayanam/evelyn-simulations.git
```

```bash
cd "evelyn-simulations/CsvProcessor Simulation"
```

The tools are listed in the repo's [README](../README.md#what-you-need). There is nothing to
install by hand: the first `uv run` in a project creates its `.venv` with Python 3.11 and the pinned
packages (like `mvn` fetching dependencies on the first build).

## 1. Tests

Two function projects, one test run each:

```bash
cd StudentSections/StudentSectionsFunction
```

```bash
uv run pytest -q
```

**Check:** `9 passed`.

```bash
cd ../StudentIntakeFunction
```

```bash
uv run pytest -q
```

**Check:** `7 passed`.

## 2. A local run

On the tenant, the functions read and write a bucket, which a laptop doesn't have. So a local run
calls the code underneath, in the order the Flows do. You're in `StudentIntakeFunction`.

**Parse the CSV**, as node **Parse CSV** does:

```bash
uv run python -c "import json, pathlib, intake; print(json.dumps({'students': [s.model_dump() for s in intake.parse_students(pathlib.Path('../../data/students.csv').read_text())]}))" > /tmp/intake-out.json
```

```bash
jq '.students | length' /tmp/intake-out.json
```

**Check:** `20`.

**Assign the sections.** Hand that list to the sections function, as **Run sections flow** does.
This one runs the function itself, through `uipath run`:

```bash
cd ../StudentSectionsFunction
```

```bash
jq '{operation: "assign_sections", students: .students}' /tmp/intake-out.json > /tmp/assign-in.json
```

```bash
uv run uipath run main --file /tmp/assign-in.json --output-file /tmp/assign-out.json
```

```bash
jq -r '.section_1[].name' /tmp/assign-out.json
```

**Check:** `Successful execution`, then ten names, from `alice Wonderland` to `John Appleseed` (the
table in [Expected result](README.md#expected-result)). `jq -r '.section_2[].name'
/tmp/assign-out.json` gives the other ten. The line `Resource overwrites config file not found` is
harmless.

Go back to the simulation folder for level 3:

```bash
cd ../..
```

## 3. On the tenant

**Needs a tenant login; not run yet.** These steps create a bucket on the tenant you're logged
into, upload a file to it and run three jobs. Use a tenant you're allowed to experiment on.

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
cd StudentSections
```

```bash
uip solution resources refresh
```

2. **First debug run: it should fail at Parse CSV.** The bucket is a Solution resource, so this
   run creates it, empty, in your personal workspace (**Inference**: debug provisions into the
   personal workspace). With no `input/students.csv` in it, **Parse CSV** fails, and the child Flow
   never starts: the same thing a bad row does.

```bash
uip maestro flow debug StudentIntakeFlow --inputs '{"csv_path": "input/students.csv"}' --output json > /tmp/intake-debug-1.json
```

It takes 1 to 5 minutes and prints only at the end. **Check:** `jq '.Data.finalStatus' /tmp/intake-debug-1.json`
says `Faulted`, and the cause names the missing file.

3. **Find the bucket and upload the CSV.**

```bash
uip or buckets list --all-folders --name StudentSectionsFiles --output json
```

Copy the bucket's key (a GUID) and its folder into two shell variables. The folder is the one
`buckets list` shows, usually your personal workspace, named `<your email>'s workspace`.

```bash
BUCKET_KEY=paste-the-key-here
```

```bash
WORKSPACE="paste-the-folder-here"
```

```bash
uip or bucket-files upload "$BUCKET_KEY" input/students.csv --folder-path "$WORKSPACE" --file ../data/students.csv --content-type text/csv
```

4. **Second debug run: the real one.**

```bash
uip maestro flow debug StudentIntakeFlow --inputs '{"csv_path": "input/students.csv"}' --output json > /tmp/intake-debug-2.json
```

**Check:**
- `jq '.Data' /tmp/intake-debug-2.json` shows `student_count` 20 and the two paths.
- In Maestro's instance view, click **Run sections flow**: its input holds the 20 students, and
  its output holds the child's four outputs.
- The child run appears as its own instance.

5. **Read the two CSVs back.**

```bash
uip or bucket-files download "$BUCKET_KEY" output/section-1.csv --folder-path "$WORKSPACE"
```

```bash
uip or bucket-files download "$BUCKET_KEY" output/section-2.csv --folder-path "$WORKSPACE"
```

**Check:** both match [Expected result](README.md#expected-result).

- **If step 2 didn't create the bucket** (`buckets list` finds nothing), create it in the personal
  workspace yourself: `uip or buckets create StudentSectionsFiles --folder-path "$WORKSPACE"`.
  Then continue with step 3.
- **Don't run `uipath auth` in a function folder.** `uip solution pack`, which `flow debug` also
  uses, ships `.env` inside the package. `uip login` keeps its login in `~/.uipath/`.
- **Run either this folder or your rebuild on the tenant, not both.** They use the same function
  and Flow names, and Orchestrator binds by name.

## 4. Deployed, and started over HTTP

**Untested.** Nobody has run this level yet. It's written from the `uip` CLI's help and source and
from the Orchestrator API docs. It deploys the Solution into an Orchestrator folder of its own, then
starts the Flow the way an outside system would: with an HTTP call. That's the UiPath form of
starting a WorkFusion BP through its REST API.

| | Level 3 | Level 4 |
|---|---|---|
| What runs | A copy uploaded to Studio Web | A published package, deployed to a folder |
| Where its files are | My Workspace | The new folder, `StudentSections Deployed` |
| What starts it | `uip maestro flow debug` | An HTTP call: curl, Postman, or another system |

Start from the simulation folder.

1. **Pack and publish** the Solution:

```bash
cd StudentSections
```

```bash
uip solution resources refresh
```

```bash
uip solution pack . /tmp/student-pack --version 1.0.0 --output json
```

```bash
uip solution publish /tmp/student-pack/StudentSections_1.0.0.zip --output json
```

**Check:** `uip solution packages list --name StudentSections --output json` lists version `1.0.0`. To
publish again after a change, pack with a higher `--version`.

2. **Deploy.** This creates the folder `StudentSections Deployed` and, in it, both Flows, both functions and an empty bucket:

```bash
uip solution deploy run -n student-sections --package-name StudentSections --package-version 1.0.0 --folder-name "StudentSections Deployed" --output json
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
curl -s --get "$BASE/odata/Folders" --data-urlencode "\$filter=contains(DisplayName,'StudentSections')" --data-urlencode '$select=Id,FullyQualifiedName' -H "Authorization: Bearer $TOKEN" | jq '.value'
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
DEPLOY_BUCKET=$(uip or buckets list --folder-path "$DEPLOY_FOLDER" --limit 100 --output plain --output-filter "[?Name=='StudentSectionsFiles'].Key | [0]")
```

```bash
uip or bucket-files upload "$DEPLOY_BUCKET" input/students.csv --folder-path "$DEPLOY_FOLDER" --file ../data/students.csv --content-type text/csv
```

**Check:** `echo "$DEPLOY_BUCKET"` printed a GUID before the upload.

6. **Find the Flow's release key.** A release is Orchestrator's name for a deployed process, and
   StartJobs asks for its key:

```bash
curl -s --get "$BASE/odata/Releases" --data-urlencode "\$filter=Name eq 'StudentIntakeFlow'" --data-urlencode '$select=Key,Name' -H "Authorization: Bearer $TOKEN" -H "X-UIPATH-OrganizationUnitId: $FOLDER_ID" | jq '.value'
```

```bash
RELEASE_KEY=paste-the-Key
```

7. **Start it.** `InputArguments` holds the Flow's `in` variables as a JSON **string**, not an
   object, so `jq` builds the body:

```bash
jq -n --arg k "$RELEASE_KEY" '{startInfo: {ReleaseKey: $k, RunAsMe: true, InputArguments: ({csv_path: "input/students.csv"} | tojson)}}' > /tmp/start-job.json
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

**Check:** `student_count` 20 and the two paths, the same as the second debug run in level 3.

Then the two CSVs, from the deployed bucket:

```bash
uip or bucket-files download "$DEPLOY_BUCKET" output/section-1.csv --folder-path "$DEPLOY_FOLDER"
```

```bash
uip or bucket-files download "$DEPLOY_BUCKET" output/section-2.csv --folder-path "$DEPLOY_FOLDER"
```

**Check:** both match [Expected result](README.md#expected-result).

10. **Remove the deployment** when you're done. This deletes the folder `StudentSections Deployed` and everything
    the deployment made in it, the bucket's files included:

```bash
uip solution deploy uninstall student-sections --yes
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
| Find the folder | `GET {{base}}/odata/Folders?$filter=contains(DisplayName,'StudentSections')` | None |
| Find the release | `GET {{base}}/odata/Releases?$filter=Name eq 'StudentIntakeFlow'` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |
| Start | `POST {{base}}/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs` | The same, plus `Content-Type: application/json` |
| Poll | `GET {{base}}/odata/Jobs({{jobId}})` | `X-UIPATH-OrganizationUnitId: {{folderId}}` |

4. **The Start request's body** (raw, JSON). `InputArguments` is a string, so its quotes are
   escaped:

```json
{"startInfo": {"ReleaseKey": "{{releaseKey}}", "RunAsMe": true, "InputArguments": "{\"csv_path\": \"input/students.csv\"}"}}
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
| One run, node by node | The Studio Web link in the debug output, for example `jq -r '.Data.studioWebUrl' /tmp/intake-debug-2.json`. The canvas opens in Debug mode. The panel at the bottom has **Spans** (one per node) and **Incidents** (the error). Click a node to see its output in its properties panel ([Debugging basics](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/debugging-effectively)) |
| Every Flow run in the tenant | Maestro → **Flow instances** (Preview) ([docs](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/flow-instances-view)). The child Flow's run should be listed separately from the parent's. Whether debug runs show up there is unverified |
| The bucket `StudentSectionsFiles` and its files | Orchestrator → **My Folders** → **My Workspace** → **Storage Buckets** tab → `StudentSectionsFiles`. Buckets belong to a folder, so they don't show while **Tenant** is selected. Look for `input/students.csv` and, after the second run, `output/section-1.csv` and `output/section-2.csv` |
| Each function's run | Orchestrator → **My Workspace** → **Automations** → **Jobs**: one job per function node (**Inference**) |

The CLI calls your personal workspace `<your email>'s workspace`. The web UI calls the same folder
**My Workspace**.

## Things only the tenant run can confirm

| Unknown | Why it matters | If it's wrong |
|---|---|---|
| Does the first debug run create the bucket, and in which folder? | Steps 2–3 rely on it | Create it by hand (above) and note the folder |
| Does a debug run of the parent also run the in-solution child? | The whole example | The node faults; read `$vars.runSectionsFlow1.error` in the instance view |
| Does the child's `students` arrive as a list of objects? | `validate` can't check run-time shapes | `Assign sections` fails with `Invalid input`; look at its input |
| Do the child's `out` variables come back as `output.section_1_path`…? | UiPath-WorkFusion's `IsaacTransactionMonitoringFlow` reads a child Flow's outputs this way (`$vars.integrateIsaacModel1.output.resultPayload`) | The parent's paths are `null`; look at the node's output |
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
