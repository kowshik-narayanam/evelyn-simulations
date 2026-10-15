# Student sections: one Flow calling another

**The point of this example:** one Maestro Flow calling another, WorkFusion's BP → BP call. The parent
Flow reads a CSV from a storage bucket and turns each row into a `Student`. It then hands the whole
list to a child Flow and waits. The child sorts the students by first name, splits them into two
sections of 10 and writes one CSV per section back to the bucket. The parent gets the two file
paths back. Each Flow has its own function project, and the `Student` contract is copied into both,
the way the Isaac port in UiPath-WorkFusion shares its contract between Functions.

```
StudentIntakeFlow (parent)
  Manual trigger ─► Parse CSV ─────────────► Run sections flow ─────────────► End
  csv_path          StudentIntakeFunction    a Flow-calls-Flow node            student_count,
                    reads input/students.csv students ─► waits ─► 2 paths ◄─┐  section_1_path,
                    out: students[20]                                       │  section_2_path
                                                                            │
StudentSectionsFlow (child)                                                 │
  Manual trigger ─► Assign sections ──────► Write CSVs ─────────────► End ──┘
  students          StudentSectionsFunction StudentSectionsFunction   section_1_path, section_2_path,
                    sort by first name,     writes output/section-1.csv section_1_count,
                    split 10 / 10           and output/section-2.csv    section_2_count
```

## Why: Evelyn's CSV processors

Evelyn never screens a raw CSV. Its CSV ingestion BP reads the file and maps each row into
`ScreenedData` and a `WleData` list, and only those reach the screening steps. This example does
the same at toy size: the raw CSV stops at the parent, and the child sees only `Student` objects.

| Evelyn (`names-screening-jnw`, package `task/csv`) | Does | Here |
|---|---|---|
| `CsvMonitorTaskProcessor` (`csv-monitor-task`) | Lists the CSV files in S3, one row per file | Not modelled: the parent takes one `csv_path` |
| `CsvTaskProcessor` (`csv-task`) | Reads the format file and a data file, maps the rows into `ScreenedData` + `List<WleData>` | `StudentIntakeFunction` (`intake.py`): reads one CSV from the bucket, maps each row into a `Student`, fails on a bad row |
| `CsvSchemaProducerProcessor` (`csv-schema-producer`) | Takes `SCREENED_DATA` + `WLE_LIST`, starts a transaction and its analytics, passes both on | No separate step: the parser already returns the contract type. No transaction or analytics |
| `ScreenedData`, `WleData` (the NSS contract) | The shape both sides agree on | `student_contract.py`, one byte-identical copy in each function project |
| The main BP | Screens; never reads the CSV | `StudentSectionsFlow`: sorts and splits; never sees the CSV |

## WorkFusion → UiPath

| WorkFusion | Here |
|---|---|
| The CSV ingestion BP and the main BP | `StudentIntakeFlow` and `StudentSectionsFlow`, two Maestro Flows in one Solution |
| `BP_CALL` to the main BP, sync, with `sendResultToCaller=true` on the callee | The node **Run sections flow**, type `uipath.core.flow.<key>`, with `fireAndForget: false`. The child's `in` variables are its inputs; the child's `out` variables come back as `$vars.runSectionsFlow1.output.<name>` |
| The callee BP's input | The child Flow's `in` variable `students` |
| An `in-contract.yaml` that two BPs agree on | `student_contract.py`, one copy in each function project, and a test that fails if they differ |
| A bot step | A function node |
| S3 | The storage bucket `StudentSectionsFiles` |
| Sorting in a task processor | `sections.py`, called by the node **Assign sections** |
| The BP designer in WorkFusion Studio | Studio Web's Flow designer ([route B](#route-b-build-the-flows-in-studio-web)), or `uip maestro flow` commands (route A, below) |

**Status (2026-10-03):**
- **Verified locally:**
  - the route A commands below, re-run as written in an empty folder;
  - 7 + 9 tests pass;
  - four deliberately wrong sort rules each fail the tests;
  - both Flows `validate` as Valid with no warnings;
  - `solution pack` is Valid.
- **Not run yet:** route B (Studio Web) and the tenant run. Nothing in this folder has been
  uploaded or run on a tenant.

## Build it yourself

Every command below, in order, builds this example from an empty folder. The code files are
copied from this folder; type them yourself if you prefer.

- **Start here:** open a terminal in this folder, the one with this README. Step 1 remembers it as
  `$EXAMPLE`.
- **Where:** the commands build in `~/rebuild/example3.1-student-sections`. Change the path in
  step 1 if you like; everything after it is relative.
- **One terminal:** run every block in the same terminal, top to bottom. `$EXAMPLE` (step 1) and
  the node types (steps 8 and 9) live in shell variables, and a new terminal forgets them.
- **Local only:** nothing in steps 1–10 changes the tenant. `uip maestro flow validate`,
  `registry` and `uip solution resources refresh` read from the tenant you're logged into, read
  only.
- **Different IDs:** your Solution, projects and functions get new IDs. Your `.flow` files match
  this folder's except for those keys.
- **Needs:** `uv`, the `uip` CLI (logged in: `uip login status`) and `jq`.

The six build steps and where they are:

| Build step | Sections | How |
|---|---|---|
| 1. Folder, Solution, both function projects | [1](#1-the-folder-and-the-input-file)–[4](#4-the-sections-function-project) | Commands. Studio Web can't create coded functions |
| 2. Code, tests, schema, the bucket binding | [5](#5-the-code)–[6](#6-tests-schema-the-bucket-binding-and-a-local-run) | Commands |
| 3. Register both functions in the Solution | [7](#7-register-both-functions) | Commands |
| 4. The child Flow, `StudentSectionsFlow`, **first** | [8](#8-the-child-flow-studentsectionsflow) (route A) or [B](#route-b-build-the-flows-in-studio-web) (route B) | Commands, or the designer |
| 5. The parent Flow, `StudentIntakeFlow`, with the Flow-calls-Flow node | [9](#9-the-parent-flow-studentintakeflow) (route A) or [B](#route-b-build-the-flows-in-studio-web) (route B) | Commands, or the designer |
| 6. `resources refresh`, then `pack --dry-run` | [10](#10-resources-and-pack) | Commands |

Why the child comes first: the parent's Flow-calls-Flow node takes its input fields from the
child's `in` variables, so the child has to declare them before the node is added.

### 1. The folder and the input file

```bash
EXAMPLE=$(pwd)
```

```bash
mkdir -p ~/rebuild/example3.1-student-sections/data
```

```bash
cd ~/rebuild/example3.1-student-sections
```

```bash
cp "$EXAMPLE/data/students.csv" data/
```

`data/students.csv` is the input: 20 students, deliberately **jumbled**. It lives outside the
Solution, so no package ever ships it; on the tenant you upload it to the bucket.

The names are mock data, nobody real: classic placeholders (Alice and Bob, John and Jane Doe, Foo
Bar, Lorem Ipsum, Eve the eavesdropper, Mallory in the middle, Bobby Tables) and tech names with
their first letters swapped (Gill Bates, Melon Eusk).

| Row | ID | Name | Age | Sorted position | Section |
|---|---|---|---|---|---|
| 1 | STU-001 | Zark Muckerberg | 15 | 20 | 2 |
| 2 | STU-002 | Gill Bates | 13 | 7 | 1 |
| 3 | STU-003 | Melon Eusk | 16 | 14 | 2 |
| 4 | STU-004 | Carol Singer | 14 | 3 | 1 |
| 5 | STU-005 | John Doe | 17 | 11 | 2 |
| 6 | STU-006 | Pundar Sichai | 13 | 17 | 2 |
| 7 | STU-007 | Eve Dropper | 15 | 5 | 1 |
| 8 | STU-008 | Tinus Lorvalds | 14 | 19 | 2 |
| 9 | STU-009 | Jeve Stobs | 16 | 9 | 1 |
| 10 | STU-010 | alice Wonderland | 13 | 1 | 1 |
| 11 | STU-011 | Mallory Middleman | 15 | 13 | 2 |
| 12 | STU-012 | Parry Lage | 17 | 16 | 2 |
| 13 | STU-013 | Dack Jorsey | 14 | 4 | 1 |
| 14 | STU-014 | Rennis Ditchie | 16 | 18 | 2 |
| 15 | STU-015 | Jane Doe | 13 | 8 | 1 |
| 16 | STU-016 | Lorem Ipsum | 17 | 12 | 2 |
| 17 | STU-017 | Bobby Tables | 14 | 2 | 1 |
| 18 | STU-018 | Natya Sadella | 15 | 15 | 2 |
| 19 | STU-019 | Foo Bar | 16 | 6 | 1 |
| 20 | STU-020 | John Appleseed | 13 | 10 | 1 |

**How jumbled, and why.**
- **No sorted neighbours touch:** rows next to each other in the file are at least 3 places apart
  once sorted. The longest ascending run is 3 rows.
- **Nothing else is sorted either:** surnames and ages are mixed too.
- **Balanced halves:** rows 1–10 hold 5 students of each section, so "first 10 rows = section 1"
  is wrong for half of them.
- **Two traps for the sort rule:**
  - `alice` is lower case, like a username. Plain sorting puts every capital before every small
    letter, so it would send her after Zark, into section 2.
  - The two Johns straddle the boundary. John Doe has the lower ID and comes first in the file,
    so a sort that breaks the tie by ID or by file order puts the wrong John in section 1.
- **A test checks all of this:** `test_the_input_file_is_jumbled` fails if anyone reorders the file
  into an easy order.

**Check:** `head -3 data/students.csv` shows the header `name,id_number,age`, then Zark Muckerberg
and Gill Bates.

### 2. The Solution

```bash
uip solution init StudentSections
```

| Creates | What it is |
|---|---|
| `StudentSections/StudentSections.uipx` | The list of projects in the Solution, like a parent `pom.xml`'s `<modules>`. Tool-managed |
| `StudentSections/AGENTS.md`, `CLAUDE.md` | `uip`'s notes for AI agents. Generated, and not this example's AI instructions: those are in [AGENTS.md](AGENTS.md) at the example root |

All four projects (two functions, two Flows) go in this one Solution. That is what lets the parent
call the child with a Flow-calls-Flow node, and lets each Flow call its function, without
publishing anything first.

**Check:** `ls StudentSections` shows `AGENTS.md`, `CLAUDE.md` and `StudentSections.uipx`.

### 3. The intake function project

```bash
cd StudentSections
```

```bash
mkdir StudentIntakeFunction
```

```bash
cd StudentIntakeFunction
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
uv run uipath new StudentIntakeFunction --type function
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

### 4. The sections function project

The same again, for the child Flow's function:

```bash
cd ..
```

```bash
mkdir StudentSectionsFunction
```

```bash
cd StudentSectionsFunction
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
uv run uipath new StudentSectionsFunction --type function
```

```bash
uv add --dev pytest
```

```bash
uv add "pydantic>=2.10,<3"
```

**Check:** the same six entries as in step 3.

**Why two function projects, not one?** Each Flow owns its code, as two WorkFusion BPs would. The
only thing they share is the contract. One project with three operations would work too, but it
would hide the question this example is about: how do two separately packaged pieces agree on a
class?

### 5. The code

```bash
cd ../StudentIntakeFunction
```

```bash
cp "$EXAMPLE"/StudentSections/StudentIntakeFunction/{main.py,intake.py,student_contract.py,test_main.py} .
```

```bash
cd ../StudentSectionsFunction
```

```bash
cp "$EXAMPLE"/StudentSections/StudentSectionsFunction/{main.py,sections.py,student_contract.py,test_main.py} .
```

| File | Project | Holds |
|---|---|---|
| `student_contract.py` | both, **byte-identical** | `Student`: `name` and `id_number` (not blank, spaces stripped), `age` 3–25 |
| `intake.py` | intake | `parse_students(csv_text)`: checks the header `name,id_number,age`, skips blank lines, fails on a bad row with its line number. Pure Python: no bucket |
| `main.py` | intake | `IntakeIn` (`csv_path`, default `input/students.csv`), `IntakeOut` (`students`, `count`). Downloads the file from the bucket, then calls `parse_students` |
| `sections.py` | sections | `sort_key`, `assign_sections`, `to_csv`. Pure Python: no bucket |
| `main.py` | sections | Two operations, each node fixing which one it runs: `assign_sections` (sort and split) and `write_csvs` (upload the two CSVs) |
| `test_main.py` | each | 7 tests (intake) and 9 tests (sections), with a fake bucket in place of the SDK |

**The sort rule** (`sections.py`): first name = the first word of `name`, compared with
`casefold()`, so case doesn't matter. Ties go to the full name, then the ID. Section 1 gets the first
half, and the extra student when the count is odd.

**Why the contract is copied, not shared:** each function is packaged on its own and can import
only the files inside its folder. An import from the other project works in pytest and then fails
on the tenant. The Isaac port in UiPath-WorkFusion copies its contract
(`isaac_contracts/models.py`) into each Function and tests that the copies match
(`Isaac/tests/foundation/test_function_projects_are_self_contained.py`); so does this example.

**Check:** `ls` in each project shows its four files next to `pyproject.toml` and `uipath.json`.

### 6. Tests, schema, the bucket binding, and a local run

Tests first, in the sections project (you're in it):

```bash
uv run pytest -q
```

**Check:** `9 passed`. One of them compares the two `student_contract.py` copies byte for byte;
another checks the input file is still jumbled.

```bash
cd ../StudentIntakeFunction
```

```bash
uv run pytest -q
```

**Check:** `7 passed`.

Generate each project's schema:

```bash
uv run uipath init
```

```bash
cd ../StudentSectionsFunction
```

```bash
uv run uipath init
```

`uipath init` writes `entry-points.json`, `bindings.json`, `main.mermaid` and more: all generated.

**The bucket binding (a hand edit).** `bindings.json` tells the Solution which Orchestrator
resources a function uses. `uipath init` leaves it empty even though the code calls
`sdk().buckets` with a literal name (checked 2026-10-03, `uipath` 2.14.27; the `--infer-bindings`
option some docs mention does not exist in this version). So add the bucket by hand. In the
sections project (you're in it), the entry is:

```json
{
  "resource": "bucket",
  "key": "StudentSectionsFiles",
  "value": {
    "name": { "defaultValue": "StudentSectionsFiles", "isExpression": false, "displayName": "Name" },
    "folderPath": { "defaultValue": "", "isExpression": false, "displayName": "Folder Path" }
  },
  "metadata": { "ActivityName": "upload", "BindingsVersion": "2.2", "DisplayLabel": "FullName" }
}
```

This `jq` command writes it, so you don't have to edit by hand:

```bash
jq '.resources = [{"resource": "bucket", "key": "StudentSectionsFiles", "value": {"name": {"defaultValue": "StudentSectionsFiles", "isExpression": false, "displayName": "Name"}, "folderPath": {"defaultValue": "", "isExpression": false, "displayName": "Folder Path"}}, "metadata": {"ActivityName": "upload", "BindingsVersion": "2.2", "DisplayLabel": "FullName"}}]' bindings.json > /tmp/sections-bindings.json
```

```bash
cp /tmp/sections-bindings.json bindings.json
```

The same for the intake project. The only difference is `"ActivityName": "download"`:

```bash
cd ../StudentIntakeFunction
```

```bash
jq '.resources = [{"resource": "bucket", "key": "StudentSectionsFiles", "value": {"name": {"defaultValue": "StudentSectionsFiles", "isExpression": false, "displayName": "Name"}, "folderPath": {"defaultValue": "", "isExpression": false, "displayName": "Folder Path"}}, "metadata": {"ActivityName": "download", "BindingsVersion": "2.2", "DisplayLabel": "FullName"}}]' bindings.json > /tmp/intake-bindings.json
```

```bash
cp /tmp/intake-bindings.json bindings.json
```

| Field | Why |
|---|---|
| `key` and `name` | The bucket's name, the same literal the code passes to `sdk().buckets` |
| `folderPath` empty | No fixed folder: the bucket belongs to the Solution and lands wherever the Solution is deployed or debug-run. Step 7 shows the result |
| `ActivityName` | The SDK call that uses it: informational |

Re-running `uipath init` keeps the entry (checked).

**Check:** `jq -c '.resources[] | {resource, key}' bindings.json` prints
`{"resource":"bucket","key":"StudentSectionsFiles"}` in both projects.

**A local run, the way the Flows chain the data.** The intake function needs the tenant's bucket,
so locally you call its parser directly. Its output is exactly what node **Parse CSV** returns:

```bash
uv run python -c "import json, pathlib, intake; print(json.dumps({'students': [s.model_dump() for s in intake.parse_students(pathlib.Path('../../data/students.csv').read_text())]}))" > /tmp/intake-out.json
```

```bash
jq '.students | length' /tmp/intake-out.json
```

**Check:** `20`.

Now hand that list to the child's first node, as **Run sections flow** will. `jq` builds the input:
the fixed operation plus the students.

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

**Check:** ten names, from `alice Wonderland` to `John Appleseed` (the table in
[Expected result](#expected-result)). `jq -r '.section_2[].name' /tmp/assign-out.json` gives
the other ten. The line `Resource overwrites config file not found` is harmless. `write_csvs`
needs the bucket, so it runs only on the tenant; `test_write_csvs_uploads_both_sections` covers it
with a fake bucket.

### 7. Register both functions

```bash
cd ..
```

```bash
uip solution projects add ./StudentIntakeFunction
```

```bash
uip solution projects add ./StudentSectionsFunction
```

Each command adds the project to `StudentSections.uipx` and writes its package and process into
`resources/`. It also reads the project's `bindings.json`.

**Check:** `find resources -type f` lists five files:
- two in `package/`;
- two in `process/function/`;
- **one** bucket, `bucket/orchestratorBucket/StudentSectionsFiles.json`.

Both functions declared the same bucket, and the Solution keeps one. Its folder is
`solution_folder`: it's a **virtual** resource that the Solution creates when it's deployed or
debug-run. You never create the bucket by hand.

### 8. The child Flow: StudentSectionsFlow

Route A, by commands. For the designer, skip to [Route B](#route-b-build-the-flows-in-studio-web)
after 8a.

**8a. Create the Flow project.** From `StudentSections/` (you're there):

```bash
uip maestro flow init StudentSectionsFlow
```

**Check:** the output shows `"Status": "Registered"`.

```bash
cd StudentSectionsFlow
```

**8b. Keep the function's node type in a shell variable.** `registry search --local` returns two
types per function: the function node and an agent-tool node. The filter picks the function
node by its `Category`.

```bash
SECTIONS=$(uip maestro flow registry search StudentSectionsFunction --local --output plain --output-filter "[?DisplayName=='StudentSectionsFunction' && Category=='function'].NodeType | [0]")
```

**Check:** `echo $SECTIONS` prints `uipath.core.function.…`.

**8c. The two function nodes and the End node.** Same node type, different fixed `operation`. A
node's ID comes from its label: `Assign sections` becomes `assignSections1`.

```bash
uip maestro flow node add StudentSectionsFlow.flow "$SECTIONS" --label "Assign sections" --input '{"operation": "assign_sections", "students": "=js:$vars.start.output.students"}'
```

```bash
uip maestro flow node add StudentSectionsFlow.flow "$SECTIONS" --label "Write CSVs" --input '{"operation": "write_csvs", "section_1": "=js:$vars.assignSections1.output.section_1", "section_2": "=js:$vars.assignSections1.output.section_2"}'
```

```bash
uip maestro flow node add StudentSectionsFlow.flow core.control.end --label "End"
```

| Node ID | `operation` (fixed) | Other inputs | Why |
|---|---|---|---|
| `assignSections1` | `assign_sections` | `students` ← `$vars.start.output.students` | The Flow's own input, i.e. what the parent sent |
| `writeCsvs1` | `write_csvs` | `section_1`, `section_2` ← `$vars.assignSections1.output.…` | The two lists node 1 made |
| `end1` | | (outputs mapped in 8f) | |

Inputs you don't set (`section_1` on node 1, `students` on node 2) are sent as `null`; `main.py`
turns `null` into an empty list, and a test covers it.

**8d. The Flow's inputs and outputs.** The `in` variable `students` becomes the input field of
any node that calls this Flow (step 9).

```bash
uip maestro flow variable add StudentSectionsFlow.flow students --direction in --type array --sub-type object --description "The students to place, as StudentIntakeFlow parsed them"
```

```bash
uip maestro flow variable add StudentSectionsFlow.flow section_1_path --direction out --type string --description "Path of section 1's CSV inside the bucket"
```

```bash
uip maestro flow variable add StudentSectionsFlow.flow section_2_path --direction out --type string --description "Path of section 2's CSV inside the bucket"
```

```bash
uip maestro flow variable add StudentSectionsFlow.flow section_1_count --direction out --type number --description "How many students are in section 1"
```

```bash
uip maestro flow variable add StudentSectionsFlow.flow section_2_count --direction out --type number --description "How many students are in section 2"
```

**8e. The edges.**

```bash
uip maestro flow edge add StudentSectionsFlow.flow start assignSections1
```

```bash
uip maestro flow edge add StudentSectionsFlow.flow assignSections1 writeCsvs1
```

```bash
uip maestro flow edge add StudentSectionsFlow.flow writeCsvs1 end1
```

**8f. Map the End node's outputs (the one hand edit).** In the node `"id": "end1"`, the
`"outputs"`:

```json
"outputs": {
  "section_1_path": { "source": "=js:$vars.writeCsvs1.output.section_1_path", "type": "string" },
  "section_2_path": { "source": "=js:$vars.writeCsvs1.output.section_2_path", "type": "string" },
  "section_1_count": { "source": "=js:$vars.assignSections1.output.section_1.length", "type": "number" },
  "section_2_count": { "source": "=js:$vars.assignSections1.output.section_2.length", "type": "number" }
}
```

The counts need no code: `.length` is plain JavaScript on the list node 1 returned. The same edit
with `jq`:

```bash
jq '(.nodes[] | select(.id == "end1")) |= (.outputs = {"section_1_path": {"source": "=js:$vars.writeCsvs1.output.section_1_path", "type": "string"}, "section_2_path": {"source": "=js:$vars.writeCsvs1.output.section_2_path", "type": "string"}, "section_1_count": {"source": "=js:$vars.assignSections1.output.section_1.length", "type": "number"}, "section_2_count": {"source": "=js:$vars.assignSections1.output.section_2.length", "type": "number"}})' StudentSectionsFlow.flow > /tmp/sections-flow.json
```

```bash
cp /tmp/sections-flow.json StudentSectionsFlow.flow
```

**8g. Check, tidy, check again.**

```bash
uip maestro flow validate StudentSectionsFlow.flow
```

```bash
uip maestro flow format StudentSectionsFlow.flow
```

```bash
uip maestro flow validate StudentSectionsFlow.flow
```

**Check:** `"Status": "Valid"` both times, with no `Warnings`. Without 8f you'd see one
`MISSING_OUTPUT_MAPPING` warning per `out` variable. `format` lays the nodes out and fills in
`variables.nodes`, which is what makes `$vars.<node>.output` resolve at run time: always run it.

### 9. The parent Flow: StudentIntakeFlow

**9a. Create the Flow project.**

```bash
cd ..
```

```bash
uip maestro flow init StudentIntakeFlow
```

```bash
cd StudentIntakeFlow
```

**9b. See the child Flow as a node type.** A Flow in the same Solution is a node type too:

```bash
uip maestro flow registry list --local --output json
```

**Check:** among the entries is `StudentSectionsFlow` with `"Category": "flow"` and a `NodeType`
of `uipath.core.flow.…`.

```bash
INTAKE=$(uip maestro flow registry search StudentIntakeFunction --local --output plain --output-filter "[?DisplayName=='StudentIntakeFunction' && Category=='function'].NodeType | [0]")
```

```bash
CHILD=$(uip maestro flow registry search StudentSectionsFlow --local --output plain --output-filter "[?DisplayName=='StudentSectionsFlow' && Category=='flow'].NodeType | [0]")
```

**Check:** `echo $INTAKE $CHILD` prints a `uipath.core.function.…` and a `uipath.core.flow.…`.

What the Flow node offers, read from the registry:

```bash
uip maestro flow registry get "$CHILD" --local --output json
```

**Check:** `inputDefinition` has `students` (the child's `in` variable from 8d) and
`fireAndForget` (default `false`); `outputDefinition` has `output` and `error`.

**9c. The nodes.**

```bash
uip maestro flow node add StudentIntakeFlow.flow "$INTAKE" --label "Parse CSV" --input '{"csv_path": "=js:$vars.start.output.csv_path"}'
```

```bash
uip maestro flow node add StudentIntakeFlow.flow "$CHILD" --label "Run sections flow" --input '{"students": "=js:$vars.parseCsv1.output.students", "fireAndForget": false}'
```

```bash
uip maestro flow node add StudentIntakeFlow.flow core.control.end --label "End"
```

| Node ID | Type | Inputs | Why |
|---|---|---|---|
| `parseCsv1` | the intake function | `csv_path` ← `$vars.start.output.csv_path` | The Flow's input |
| `runSectionsFlow1` | **Flow-calls-Flow** | `students` ← `$vars.parseCsv1.output.students`; `fireAndForget: false` | The whole list goes to the child as one value. `false` = wait for the child and get its outputs back: WorkFusion's sync `BP_CALL` with `sendResultToCaller` |
| `end1` | | (outputs mapped in 9f) | |

`node add` also writes the child Flow's two **bindings** (its name and folder, with
`"resourceSubType": "Flow"`) into the file's `bindings`. Nothing to hand-edit: check with
`jq -c '.bindings[] | {default, resourceSubType}' StudentIntakeFlow.flow`.

**9d. The Flow's inputs and outputs.**

```bash
uip maestro flow variable add StudentIntakeFlow.flow csv_path --direction in --type string --default-value "input/students.csv" --description "Path of the student CSV inside the StudentSectionsFiles bucket"
```

```bash
uip maestro flow variable add StudentIntakeFlow.flow student_count --direction out --type number --description "How many students the CSV held"
```

```bash
uip maestro flow variable add StudentIntakeFlow.flow section_1_path --direction out --type string --description "Section 1's CSV, as StudentSectionsFlow returned it"
```

```bash
uip maestro flow variable add StudentIntakeFlow.flow section_2_path --direction out --type string --description "Section 2's CSV, as StudentSectionsFlow returned it"
```

**9e. The edges.**

```bash
uip maestro flow edge add StudentIntakeFlow.flow start parseCsv1
```

```bash
uip maestro flow edge add StudentIntakeFlow.flow parseCsv1 runSectionsFlow1
```

```bash
uip maestro flow edge add StudentIntakeFlow.flow runSectionsFlow1 end1
```

**9f. Map the End node's outputs.** The two paths come **from the child**, through the Flow
node's `output`:

```json
"outputs": {
  "student_count": { "source": "=js:$vars.parseCsv1.output.count", "type": "number" },
  "section_1_path": { "source": "=js:$vars.runSectionsFlow1.output.section_1_path", "type": "string" },
  "section_2_path": { "source": "=js:$vars.runSectionsFlow1.output.section_2_path", "type": "string" }
}
```

```bash
jq '(.nodes[] | select(.id == "end1")) |= (.outputs = {"student_count": {"source": "=js:$vars.parseCsv1.output.count", "type": "number"}, "section_1_path": {"source": "=js:$vars.runSectionsFlow1.output.section_1_path", "type": "string"}, "section_2_path": {"source": "=js:$vars.runSectionsFlow1.output.section_2_path", "type": "string"}})' StudentIntakeFlow.flow > /tmp/intake-flow.json
```

```bash
cp /tmp/intake-flow.json StudentIntakeFlow.flow
```

**9g. Check, tidy, check again.**

```bash
uip maestro flow validate StudentIntakeFlow.flow
```

```bash
uip maestro flow format StudentIntakeFlow.flow
```

```bash
uip maestro flow validate StudentIntakeFlow.flow
```

**Check:** `"Status": "Valid"`, no `Warnings`.

### 10. Resources and pack

```bash
cd ..
```

```bash
uip solution resources refresh
```

**Check:** `"Status": "Synced 0 resources (2 already in solution)"`. Nothing new: the bucket and
the processes were already declared in step 7. On the tenant, run this again before every debug
run.

```bash
uip solution resources list --source local
```

**Check:** `StudentSectionsFiles` (kind `bucket`), four packages and four processes, all in
`solution_folder`.

```bash
uip solution pack . --dry-run
```

**Check:** `"Status": "Valid"`. This builds all four projects the way a deploy would, without
writing a package.

## Route B: build the Flows in Studio Web

The same two Flows, drawn on the Studio Web canvas instead of built by commands. **Not run yet:**
it needs the tenant, so it's yours to try. The UI names below come from UiPath's docs
([canvas](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/canvas-overview),
[variables](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/variables-and-data-flow)).
Write what you actually see in `notes.md`.

**B1. Start from steps 1–7, plus two empty Flows.** Studio Web can't create coded functions, so they
arrive from your machine. Build in a fresh folder (say `~/rebuild/example3.1-route-b`): steps 1–7,
then 8a and 9a, and nothing else from steps 8 and 9.

**B2. Upload the Solution.** From `StudentSections/`:

```bash
uip solution upload .
```

**Check:**
- The output has a `DesignerUrl`.
- The Solution is in Studio Web's **Cloud workspace** tab.
- The upload also writes Studio Web's `SolutionId` into your local `.uipx`. That is how the next
  upload updates the same Solution instead of making a second one.

**B3. Draw the child, StudentSectionsFlow.**
1. Open the Flow. Select the **Manual trigger** and add an input `students`, type **Array**.
   Inputs live on the trigger node, outputs on the End node, and other variables in the
   **Variables panel**.
2. Click **+** on the trigger's outgoing handle to open the node palette. Under **Function**,
   pick `StudentSectionsFunction`. Label it `Assign sections`.
3. In the **properties panel**, **Parameters** tab, set:
   - `operation`: the text `assign_sections`;
   - `students`: the expression `$vars.start.output.students`.
4. **Node names.** The canvas names a node by its type (`function1`), not by its label as
   `node add` does. Read the name the canvas gave it, and use that name wherever this README says
   `assignSections1`.
5. **+** again → **Function** → `StudentSectionsFunction`, labelled `Write CSVs`:
   - `operation` = `write_csvs`;
   - `section_1` = `$vars.<node 1's name>.output.section_1`, and `section_2` the same way.
6. Add an **End** node. On it, add the four outputs of 8d, each with the value from 8f.

**B4. Draw the parent, StudentIntakeFlow.**
1. On the **Manual trigger**, add an input `csv_path`, type **String**, default
   `input/students.csv`.
2. **+** → **Function** → `StudentIntakeFunction`, labelled `Parse CSV`:
   `csv_path` = `$vars.start.output.csv_path`.
3. **+** → **Maestro flow** → `StudentSectionsFlow`, labelled `Run sections flow`.
   - Its Parameters should show `students`, the child's input. Set it to
     `$vars.<Parse CSV's name>.output.students`.
   - Leave **fire and forget** off. Its exact label is unknown; note it.
4. **End** node with the three outputs of 9d, values as in 9f, using the canvas's node names.

**B5. Bring it back and compare.** The `SolutionId` is in your `.uipx`:

```bash
uip solution download $(jq -r .SolutionId StudentSections.uipx) -d /tmp/route-b --extract
```

```bash
find /tmp/route-b -name "*.flow"
```

Validate each downloaded `.flow` with `uip maestro flow validate <path>`. Compare its nodes with
route A's, in this folder (`$EXAMPLE` from step 1; in a new terminal, set it again):

```bash
jq -c '.nodes[] | {id, type, inputs}' "$EXAMPLE/StudentSections/StudentIntakeFlow/StudentIntakeFlow.flow"
```

Run the same `jq` on the downloaded `StudentIntakeFlow.flow`. Expect different node IDs and keys.
Note anything else the designer wrote that the commands didn't, such as layout, extra
`variables` or bindings.

**Warning:** `uip maestro flow debug` uploads your **local** Solution over the Studio Web one. After
drawing in the designer, download first; a debug run from the local folder replaces your
drawing with whatever is on disk.

## What you end up with

```
example3.1-student-sections/
├── README.md, AGENTS.md, CLAUDE.md, notes.md         (docs; AGENTS.md is for AI agents)
├── data/students.csv                    ← the jumbled input            (yours; not packed)
└── StudentSections/                     the Solution
    ├── StudentSections.uipx             the four projects              (tool-managed)
    ├── resources/solution_folder/       packages, processes, the bucket (tool-managed)
    ├── AGENTS.md, CLAUDE.md             uip's notes for AI agents      (generated)
    ├── StudentIntakeFlow/StudentIntakeFlow.flow       ← the parent Flow (the source)
    ├── StudentSectionsFlow/StudentSectionsFlow.flow   ← the child Flow  (the source)
    ├── StudentIntakeFunction/
    │   ├── main.py, intake.py, student_contract.py, test_main.py      (yours)
    │   ├── bindings.json                ← the bucket entry is yours; the rest generated
    │   └── entry-points.json, main.mermaid, project.uiproj, uv.lock, .env, .agent/,
    │       .claude/, AGENTS.md, CLAUDE.md, .uipath/, .venv/            (generated)
    └── StudentSectionsFunction/         the same, with sections.py instead of intake.py
```

There is no `.bpmn`: `uip` generates it from each `.flow` when it packs. Each Flow folder also has
`operate.json` and `project.uiproj` (generated).

**StudentIntakeFlow (parent)**

| Direction | Variable | Type | Notes |
|---|---|---|---|
| In | `csv_path` | string | Default `input/students.csv`, a path inside the bucket |
| Out | `student_count` | number | From Parse CSV |
| Out | `section_1_path`, `section_2_path` | string | From the child Flow |

**StudentSectionsFlow (child)**

| Direction | Variable | Type | Notes |
|---|---|---|---|
| In | `students` | array of objects | Each object is a `Student`: `name`, `id_number`, `age` |
| Out | `section_1_path`, `section_2_path` | string | `output/section-1.csv`, `output/section-2.csv` |
| Out | `section_1_count`, `section_2_count` | number | 10 and 10 |

**Jobs per run: 3**: Parse CSV, Assign sections and Write CSVs, one job each. The Flow-calls-Flow
node starts a child Flow **instance** rather than a function job. **Inference:** it shows in Maestro as its
own instance, linked to the parent.

## Expected result

For `data/students.csv`:
- the parent returns `student_count` 20, `section_1_path` `output/section-1.csv` and
  `section_2_path` `output/section-2.csv`;
- the child returns the same two paths, `section_1_count` 10 and `section_2_count` 10.

`output/section-1.csv`:

```csv
name,id_number,age
alice Wonderland,STU-010,13
Bobby Tables,STU-017,14
Carol Singer,STU-004,14
Dack Jorsey,STU-013,14
Eve Dropper,STU-007,15
Foo Bar,STU-019,16
Gill Bates,STU-002,13
Jane Doe,STU-015,13
Jeve Stobs,STU-009,16
John Appleseed,STU-020,13
```

`output/section-2.csv`:

```csv
name,id_number,age
John Doe,STU-005,17
Lorem Ipsum,STU-016,17
Mallory Middleman,STU-011,15
Melon Eusk,STU-003,16
Natya Sadella,STU-018,15
Parry Lage,STU-012,17
Pundar Sichai,STU-006,13
Rennis Ditchie,STU-014,16
Tinus Lorvalds,STU-008,14
Zark Muckerberg,STU-001,15
```

Computed by running `sections.py` on the data file; the tests assert the same names.

## Run it on the tenant

**Needs a tenant login; not run yet.** These steps create a bucket on the tenant you're logged
into, upload a file to it and run three jobs.

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

**Check:** both match [Expected result](#expected-result).

- **If step 2 didn't create the bucket** (`buckets list` finds nothing), create it in the personal
  workspace yourself: `uip or buckets create StudentSectionsFiles --folder-path "$WORKSPACE"`.
  Then continue with step 3.
- **Don't run `uipath auth` in a function folder.** `uip solution pack`, which `flow debug` also
  uses, ships `.env` inside the package. `uip login` keeps its login in `~/.uipath/`.
- **Run either this folder or your rebuild on the tenant, not both.** They use the same function
  and Flow names, and Orchestrator binds by name.

**Things only the tenant run can confirm**

| Unknown | Why it matters | If it's wrong |
|---|---|---|
| Does the first debug run create the bucket, and in which folder? | Steps 2–3 rely on it | Create it by hand (above) and note the folder |
| Does a debug run of the parent also run the in-solution child? | The whole example | The node faults; read `$vars.runSectionsFlow1.error` in the instance view |
| Does the child's `students` arrive as a list of objects? | `validate` can't check run-time shapes | `Assign sections` fails with `Invalid input`; look at its input |
| Do the child's `out` variables come back as `output.section_1_path`…? | UiPath-WorkFusion's `IsaacTransactionMonitoringFlow` reads a child Flow's outputs this way (`$vars.integrateIsaacModel1.output.resultPayload`) | The parent's paths are `null`; look at the node's output |

## Try this

1. **Fire and forget.** In `StudentIntakeFlow.flow`, set the Flow node's `"fireAndForget": true`,
   `validate`, and debug again (step 4).
   - Does the parent's End still get the two paths?
   - What does `runSectionsFlow1.output` hold: nothing, a job key, an instance id?
   - Are the CSVs still written?

   Not observed yet; write what you see in `notes.md`. Evelyn's CSV ingestion BP → main BP call
   is this kind: asynchronous, and it never reads the main BP's result.
2. **A bad row.** Add `Test Student,STU-099,40` to the CSV, upload it, debug.
   - Locally, `parse_students` says `Line 22: … age … less than or equal to 25`.
   - Where does Maestro show it?
   - Does the child Flow start?
3. **A 21st student.** Add a valid row and upload. Section 1 gets 11. Which student?
4. **Surname order.** Change `sort_key` to use the last word, run the sections tests, and read which
   ones fail and why.
5. **Another way in.** A Flow input can be a `file`, bound with
   `uip maestro flow debug … --attachment <variable>=<path>` (`uip maestro flow debug --help`).
   That is closer to WorkFusion's file-upload input channel than a bucket path is. Not tried.

## What building it taught

| Finding | Evidence | What was done |
|---|---|---|
| A Flow in the same Solution is a node type, `uipath.core.flow.<key>`, category `flow` | `uip maestro flow registry list --local` after `flow init StudentSectionsFlow` | Used it as **Run sections flow** |
| The child's `in` variables become the Flow node's inputs, plus `fireAndForget` (default `false`). Its outputs are `output` and `error` | `registry get "$CHILD" --local`: `inputDefinition` = `students`, `fireAndForget` | Bound `students` with one expression |
| `node add` writes the child Flow's bindings (`resourceSubType: "Flow"`) | `jq '.bindings' StudentIntakeFlow.flow` after `node add` | No hand edit: the CLI writes them |
| `uipath init` does not record a bucket in `bindings.json`, even for a literal name; `--infer-bindings` doesn't exist in 2.14.27 | `bindings.json` stayed `"resources": []`; `uipath init --infer-bindings` → `No such option` | Hand-added the entry (step 6); `init` keeps it on re-runs |
| Two functions binding the same bucket give the Solution **one** bucket, a virtual one in `solution_folder` | `find resources -type f` after `projects add`; `resources list --source local` | No `buckets create` in the plan; the deploy or debug run makes it |
| `registry search` returns two node types per function or Flow: the node, and an agent tool | `--output table` shows both rows | The filters pick by `Category` |
| `uip` can upload and download bucket files | `uip or bucket-files --help`: `upload`, `download` | The tenant steps need no Orchestrator UI |
| The tests catch a wrong sort rule | Four mutations (no `casefold`, tie by ID, tie by file order, surname) each failed `test_the_twenty_students_split_into_the_expected_sections` | Kept the jumbled data and its guard test |
| The Studio Web canvas names nodes by type, not by label | [Variables docs](https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/variables-and-data-flow): "auto-assigned based on the node type" | Route B tells you to read the names it gives |
| `flow debug` uploads the local Solution over the Studio Web one | `uip maestro flow debug --help`: "Debug a flow project by uploading to Studio Web" | The warning in Route B |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `9 passed` becomes `8 passed, 1 failed` on the contract test | The two `student_contract.py` copies differ | Copy the edited one over the other |
| `test_the_input_file_is_jumbled` fails | `data/students.csv` was reordered or edited | Restore it from this folder |
| `echo $SECTIONS` / `$CHILD` prints nothing | New terminal, or the project isn't in the Solution | Re-run step 7 (functions) or 8a (the child Flow), then the lookup |
| `node add` for **Run sections flow** fails, unknown node type | The child Flow wasn't created first | Do step 8 before step 9 |
| `validate`: `MISSING_OUTPUT_MAPPING` | 8f or 9f not done | Do it |
| Node IDs end in `2` | A node added twice | Start again from step 1 in an empty folder |
| `find resources` shows no bucket | `bindings.json` had no bucket entry when you ran `projects add` | Add the entry (step 6), then `uip solution resources refresh` |
| Debug: Parse CSV fails, file not found | The CSV isn't in the bucket yet, or is in another folder's bucket | Tenant step 3 |
| Debug: the paths come back `null` | The child's End outputs aren't mapped, or the parent reads the wrong field | 8f, then 9f |
| `Resource overwrites config file not found` | Harmless noise from `uipath run` | Ignore |

## Done when

- [ ] `uv run pytest -q` passes in both function projects (7 and 9).
- [ ] The local chain (step 6) prints section 1 from `alice Wonderland` to `John Appleseed`.
- [ ] Both Flows `validate` as Valid with no warnings, and `uip solution pack . --dry-run` is Valid.
- [ ] You can say which file is the contract, why there are two copies, and what stops them
  drifting.
- [ ] **On the tenant:**
  - the second debug run returns `student_count` 20 and two paths;
  - the two CSVs in the bucket match [Expected result](#expected-result);
  - `notes.md` answers the fire-and-forget question.
- [ ] **Route B:** both Flows drawn in Studio Web, downloaded, validated, and the
  differences from route A noted.
