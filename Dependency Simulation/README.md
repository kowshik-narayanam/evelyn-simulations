# Dependency simulation: a library shipped inside a function

**The point of this example:** Evelyn doesn't do everything in its own code. It calls libraries
built and versioned somewhere else: the `fircosoft-trust` jar for the Firco Trust connector, and
`address-lookup-jnw` for address lookups. Each is a separate project, published as a jar with a
version, declared in a `pom.xml`, and bundled into Evelyn's package. This example does the same
in Python, at toy size.

- **The library:** `evsim-calc`, its own project in `evsim-calc/`, with its own version (1.0.0) and
  tests. It has one function: `calculate(integer_1, integer_2, operand)` returns an integer.
- **Built as a binary:** `uv build` turns it into a wheel, `evsim_calc-1.0.0-py3-none-any.whl`. A
  wheel is Python's jar: a zip of the code plus its name and version.
- **Shipped inside the function:** the wheel is copied into the function's `wheels/` folder. The
  function's `pyproject.toml` declares `evsim-calc==1.0.0`, and `uv.lock` pins that exact file by
  its sha256.
- **Used by a Flow:** one node reads a CSV of 10 rows (`integer_1`, `integer_2`, `operand`) from a
  storage bucket and hands each row to the library.

```
DependencySimFlow
  Manual trigger ─► Calculate ───────────────────────────────► End
  csv_path          DependencySimFunction: reads the CSV from    results, count,
                    the bucket, calls evsim_calc.calculate()     library_version
                    once per row
                          │ imports
                          ▼
                    evsim-calc 1.0.0, installed from
                    DependencySimFunction/wheels/evsim_calc-1.0.0-py3-none-any.whl
```

| Evelyn (WorkFusion) | Here |
|---|---|
| `fircosoft-trust` and `address-lookup-jnw`: jars built in their own repos and published to WorkFusion's Nexus (the `internal` repository, root `pom.xml:741-743`) | `evsim-calc`: a library in its own project, `evsim-calc/`, built into a wheel |
| A `<dependency>` with a version property: `fircosoft-trust` `4.3.0` (`names-screening-firco-trust-connector/pom.xml:19, 23-27`), `address-lookup-jnw` `4.3.0` (`names-screening-package/pom.xml:39-42`, root `pom.xml:24`) | `"evsim-calc==1.0.0"` in the function's `pyproject.toml` |
| Maven fetches the jar from Nexus and checks its checksum | `[tool.uv.sources]` points at `wheels/evsim_calc-1.0.0-py3-none-any.whl`, and `uv.lock` records that path and the wheel's sha256 |
| The package's assembly copies the `address-lookup-jnw` jar into the package zip (`names-screening-package/assembly/names-screening-package.xml:79-81`) | The wheel sits inside the function folder, so `uip solution pack` puts it in the function's package, at `content/wheels/` |
| The connector module depends on the jar, and `names-screening-jnw` depends on the connector (`names-screening-jnw/pom.xml:31`) | `main.py` imports `evsim_calc` and calls `calculate()` |
| Java's `int` division truncates toward zero: `-7 / 2` is `-3` | `divide` does the same. Python's `//` would give `-4`: the classic trap of a Java-to-Python port |

| Maven | uv |
|---|---|
| `pom.xml` | `pyproject.toml` |
| `<dependency>` with a `<version>` | `dependencies = ["evsim-calc==1.0.0"]` |
| A repository such as Nexus | `[tool.uv.sources]` (here a file path), or a package index |
| The resolved versions and checksums | `uv.lock` |
| `mvn package` → a `.jar` | `uv build --wheel` → a `.whl` |
| `mvn dependency:tree` | `uv tree` |
| `mvn test` | `uv run pytest` |

Evelyn line numbers are from `names-screening` `master` @ `6dcf7f9d3` (2026-09-24). The model repo
`nss-classification-model` isn't used here.

**Status (2026-10-16):**
- **Verified locally:**
  - the build commands below, re-run as written in an empty folder;
  - 18 library tests and 10 function tests pass;
  - three deliberate mistakes are caught: Python's `//` for `divide` fails 2 library tests and the
    function's expected results; a different wheel under the same version 1.0.0 is refused by `uv`
    itself (`Hash mismatch`); a dependency on the library's source folder instead of the wheel
    fails 2 function tests;
  - the wheel is reproducible: two builds of the same source have the same sha256;
  - the Flow `validate`s as Valid with no warnings;
  - a real `uip solution pack` puts the wheel, `pyproject.toml` and `uv.lock` inside the function's
    package.
- **Not run yet:** the tenant run. Whether the tenant installs the library from the wheel is the
  first thing it has to confirm: see [Things only the tenant run can confirm](HOW_TO_RUN.md#things-only-the-tenant-run-can-confirm).

## How the library travels

| # | Step | Where | Like Maven's |
|---|---|---|---|
| 1 | Build the wheel | `evsim-calc/dist/evsim_calc-1.0.0-py3-none-any.whl` | `mvn package` |
| 2 | Copy it into the function | `DependencySimFunction/wheels/` | Nexus, but inside the project |
| 3 | Declare it, pinned | `pyproject.toml`: `"evsim-calc==1.0.0"` and `[tool.uv.sources]` | `<dependency>` and `<version>` |
| 4 | Lock it | `uv.lock`: version 1.0.0, the path, the sha256 | The checksum check |
| 5 | Pack it | The function's `.nupkg`: `content/wheels/…whl`, `content/uv.lock` | The assembly copying the jar into the zip |
| 6 | Install it on the tenant | The job installs the function's dependencies from `uv.lock` (**Inference**: not run yet) | The worker loading the jar |

**Why the wheel goes inside the function folder:** `uip solution pack` packs each function's own
folder and nothing outside it. A dependency on `../../evsim-calc` works on your laptop and is
missing on the tenant. [Try this](#try-this) 3 shows it.

**Why the name matters:** `evsim-calc` isn't on PyPI (HTTP 404 on 2026-10-16). If a robot ever
looked for `evsim-calc==1.0.0` on PyPI instead of in the package, it would fail, not install a
stranger's package of the same name. Give a private library a name nobody has published.

## Build it yourself

Every command below, in order, builds this example from an empty folder. The code files are
copied from this folder; type them yourself if you prefer.

- **Start here:** open a terminal in this folder, the one with this README. Step 1 remembers it as
  `$EXAMPLE`.
- **Where:** the commands build in `~/rebuild/dependency-simulation`. Change the path in step 1 if
  you like; everything after it is relative.
- **One terminal:** run every block in the same terminal, top to bottom. `$EXAMPLE` (step 1) and
  the function's node type (step 8) live in shell variables, and a new terminal forgets them.
- **Local only:** nothing in steps 1–9 changes the tenant. `uip maestro flow validate`, `registry`,
  `uip solution resources refresh` and `pack` read from the tenant you're logged into, read only.
- **Different IDs:** your Solution, projects and function get new IDs. Your `.flow` matches this
  folder's except for those keys.
- **Needs:** `uv`, the `uip` CLI (logged in: `uip login status`), `jq` and `unzip`.

| Build step | Section |
|---|---|
| The folder and the data | [1](#1-the-folder-and-the-input-file) |
| The library: its project, tests and wheel | [2](#2-the-library-evsim-calc) |
| The Solution and the function project | [3](#3-the-solution)–[4](#4-the-function-project) |
| Ship the library into the function | [5](#5-ship-the-library-into-the-function) |
| The code, the tests, the bucket binding, a local run | [6](#6-the-code-tests-schema-and-a-local-run) |
| Register the function, then the Flow | [7](#7-register-the-function)–[8](#8-the-flow-dependencysimflow) |
| `resources refresh`, then pack and look inside | [9](#9-resources-and-pack) |

### 1. The folder and the input file

```bash
EXAMPLE=$(pwd)
```

```bash
mkdir -p ~/rebuild/dependency-simulation/data
```

```bash
cd ~/rebuild/dependency-simulation
```

```bash
cp "$EXAMPLE/data/calculations.csv" data/
```

`data/calculations.csv` lives outside the Solution, so no package ships it; on the tenant you
upload it to the bucket.

| Row | `integer_1` | `integer_2` | `operand` | Result | Why it's there |
|---|---|---|---|---|---|
| 1 | 12 | 30 | add | 42 | |
| 2 | -5 | 8 | add | 3 | A negative |
| 3 | 100 | 58 | subtract | 42 | |
| 4 | 3 | 10 | subtract | -7 | A negative result |
| 5 | 7 | 6 | multiply | 42 | |
| 6 | -4 | 25 | multiply | -100 | |
| 7 | 84 | 4 | divide | 21 | Exact division |
| 8 | -7 | 2 | divide | **-3** | **The trap:** Java truncates toward zero; Python's `-7 // 2` is -4 |
| 9 | 7 | -2 | divide | **-3** | The same trap, the other sign |
| 10 | 0 | 5 | divide | 0 | |

**Check:** `head -3 data/calculations.csv` shows `integer_1,integer_2,operand`, then `12,30,add`
and `-5,8,add`.

### 2. The library: evsim-calc

The library gets a project of its own, next to the Solution and not inside it, the way
`fircosoft-trust` has its own repo:

```bash
uv init --lib --vcs none --no-readme --author-from none --python 3.11 --description "A tiny calculator library, shipped to a coded function as a wheel" evsim-calc
```

```bash
cd evsim-calc
```

```bash
uv version 1.0.0
```

| Flag | Why |
|---|---|
| `--lib` | A library: code under `src/evsim_calc/`, and a `[build-system]` (`uv_build`) so it can be built into a wheel |
| `--vcs none`, `--no-readme` | No nested git repo, no placeholder README |
| `--author-from none` | Otherwise `uv` copies your git name and email into `authors`, and they ship inside the wheel |

Now the code and its tests:

```bash
cp "$EXAMPLE/evsim-calc/src/evsim_calc/__init__.py" src/evsim_calc/
```

```bash
mkdir tests
```

```bash
cp "$EXAMPLE/evsim-calc/tests/test_calculate.py" tests/
```

```bash
uv add --dev pytest
```

```bash
uv run pytest -q
```

**Check:** `18 passed`.

| In `src/evsim_calc/__init__.py` | What it does |
|---|---|
| `calculate(integer_1, integer_2, operand)` | `add`, `subtract`, `multiply`, `divide`; returns an `int`. `divide` truncates toward zero, as Java does. Division by zero raises `ZeroDivisionError`, an unknown operand a `ValueError` that lists the four. `True`, `2.5` or `"2"` raise `TypeError` |
| `OPERANDS` | The four operands, in order |
| `__version__` | Read from the installed package's metadata, so it always matches `pyproject.toml` |

Build the wheel:

```bash
uv build --wheel
```

**Check:** `Successfully built dist/evsim_calc-1.0.0-py3-none-any.whl`. Then
`unzip -l dist/evsim_calc-1.0.0-py3-none-any.whl` lists `evsim_calc/__init__.py`, `py.typed` and
the `evsim_calc-1.0.0.dist-info/` metadata: the wheel is a zip, like a jar.

### 3. The Solution

```bash
cd ..
```

```bash
uip solution init DependencySim
```

**Check:** `ls` shows `data`, `DependencySim` and `evsim-calc`. Those `AGENTS.md`/`CLAUDE.md` in
`DependencySim/` are `uip`'s generated notes, not this example's: its own are at the example root.

### 4. The function project

```bash
cd DependencySim
```

```bash
mkdir DependencySimFunction
```

```bash
cd DependencySimFunction
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
uv run uipath new DependencySimFunction --type function
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

### 5. Ship the library into the function

This is the step the example is about. Copy the wheel **into** the function folder, then add it as
a dependency:

```bash
mkdir wheels
```

```bash
cp ../../evsim-calc/dist/evsim_calc-1.0.0-py3-none-any.whl wheels/
```

```bash
uv add ./wheels/evsim_calc-1.0.0-py3-none-any.whl
```

```bash
uv add "evsim-calc==1.0.0"
```

The first `uv add` installs the wheel and records where it comes from; the second pins the version.
`pyproject.toml` now has:

```toml
dependencies = [
    "evsim-calc==1.0.0",
    ...
]

[tool.uv.sources]
evsim-calc = { path = "wheels/evsim_calc-1.0.0-py3-none-any.whl" }
```

and `uv.lock` has:

```toml
[[package]]
name = "evsim-calc"
version = "1.0.0"
source = { path = "wheels/evsim_calc-1.0.0-py3-none-any.whl" }
wheels = [
    { filename = "evsim_calc-1.0.0-py3-none-any.whl", hash = "sha256:…" },
]
```

**Check:** `grep -A5 'name = "evsim-calc"' uv.lock` shows the block above, and
`uv tree --depth 1` lists `evsim-calc v1.0.0`. The path is relative to the function folder, so it
still holds once the folder is packed and unpacked somewhere else.

### 6. The code, tests, schema and a local run

```bash
cp "$EXAMPLE"/DependencySim/DependencySimFunction/{main.py,calculations.py,test_main.py} .
```

| File | Holds |
|---|---|
| `calculations.py` | `parse_calculations(csv_text)`: checks the header `integer_1,integer_2,operand`, skips blank lines, fails on a bad row with its line number. Pure Python: no bucket, no library |
| `main.py` | `CalculateIn` (`csv_path`, default `input/calculations.csv`), `CalculateOut` (`results`, `count`, `library_version`). Downloads the file from the bucket `DependencySimFiles`, then calls `evsim_calc.calculate()` per row. A row the library refuses fails with its line number |
| `test_main.py` | 10 tests, with a fake bucket. Two of them check the dependency itself: the library is imported from `.venv`, installed from `wheels/`; and `uv.lock`'s sha256 matches the wheel in `wheels/` |

```bash
uv run pytest -q
```

**Check:** `10 passed`.

```bash
uv run uipath init
```

`uipath init` writes `entry-points.json`, `bindings.json`, `main.mermaid` and more: all generated.
It also writes an empty `.env`; keep it empty, because `pack` ships it.

**The bucket binding (a hand edit).** `uipath init` leaves `bindings.json` empty, so add the bucket
the code downloads from:

```bash
jq '.resources = [{"resource": "bucket", "key": "DependencySimFiles", "value": {"name": {"defaultValue": "DependencySimFiles", "isExpression": false, "displayName": "Name"}, "folderPath": {"defaultValue": "", "isExpression": false, "displayName": "Folder Path"}}, "metadata": {"ActivityName": "download", "BindingsVersion": "2.2", "DisplayLabel": "FullName"}}]' bindings.json > bindings.json.tmp
```

```bash
mv bindings.json.tmp bindings.json
```

**Check:** `jq -c '.resources[] | {resource, key}' bindings.json` prints
`{"resource":"bucket","key":"DependencySimFiles"}`.

**A local run.** The function needs the tenant's bucket, so locally you call the parser and the
library directly, the same calls `main` makes:

```bash
uv run python -c "import pathlib, evsim_calc, calculations; [print(r.integer_1, r.operand, r.integer_2, '=', evsim_calc.calculate(r.integer_1, r.integer_2, r.operand)) for r in calculations.parse_calculations(pathlib.Path('../../data/calculations.csv').read_text())]; print('evsim-calc', evsim_calc.__version__)"
```

**Check:** ten lines, from `12 add 30 = 42` to `0 divide 5 = 0`, with `-7 divide 2 = -3`, then
`evsim-calc 1.0.0`. Then the trap the library avoids:

```bash
uv run python -c "print(-7 // 2, int(-7 / 2))"
```

**Check:** `-4 -3`. Python's `//` rounds down; Java, and `evsim-calc`, truncate toward zero.

### 7. Register the function

```bash
cd ..
```

```bash
uip solution projects add ./DependencySimFunction
```

**Check:** `find resources -type f` lists three files: the function's package and process, and the
bucket `bucket/orchestratorBucket/DependencySimFiles.json`. The bucket is a **virtual** resource
in `solution_folder`: the Solution creates it when it's deployed or debug-run.

### 8. The Flow: DependencySimFlow

**8a. Create the Flow project.**

```bash
uip maestro flow init DependencySimFlow
```

```bash
cd DependencySimFlow
```

**8b. Find the function's node type.**

```bash
FN=$(uip maestro flow registry search DependencySimFunction --local --output plain --output-filter "[?DisplayName=='DependencySimFunction' && Category=='function'].NodeType | [0]")
```

**Check:** `echo $FN` prints `uipath.core.function.…`.

**8c. The nodes.**

```bash
uip maestro flow node add DependencySimFlow.flow "$FN" --label "Calculate" --input '{"csv_path": "=js:$vars.start.output.csv_path"}'
```

```bash
uip maestro flow node add DependencySimFlow.flow core.control.end --label "End"
```

| Node ID | Type | Inputs |
|---|---|---|
| `calculate1` | the function | `csv_path` ← `$vars.start.output.csv_path`, the Flow's input |
| `end1` | | outputs mapped in 8f |

**8d. The Flow's inputs and outputs.**

```bash
uip maestro flow variable add DependencySimFlow.flow csv_path --direction in --type string --default-value "input/calculations.csv" --description "Path of the calculations CSV inside the DependencySimFiles bucket"
```

```bash
uip maestro flow variable add DependencySimFlow.flow results --direction out --type array --sub-type object --description "One entry per CSV row: line, integer_1, integer_2, operand and the library's result"
```

```bash
uip maestro flow variable add DependencySimFlow.flow count --direction out --type number --description "How many rows were calculated"
```

```bash
uip maestro flow variable add DependencySimFlow.flow library_version --direction out --type string --description "The evsim-calc version the function imported"
```

**8e. The edges.**

```bash
uip maestro flow edge add DependencySimFlow.flow start calculate1
```

```bash
uip maestro flow edge add DependencySimFlow.flow calculate1 end1
```

**8f. Map the End node's outputs**, all three from the function's output:

```bash
jq '(.nodes[] | select(.id == "end1")) |= (.outputs = {"results": {"source": "=js:$vars.calculate1.output.results", "type": "array"}, "count": {"source": "=js:$vars.calculate1.output.count", "type": "number"}, "library_version": {"source": "=js:$vars.calculate1.output.library_version", "type": "string"}})' DependencySimFlow.flow > DependencySimFlow.flow.tmp
```

```bash
mv DependencySimFlow.flow.tmp DependencySimFlow.flow
```

**8g. Check, tidy, check again.**

```bash
uip maestro flow validate DependencySimFlow.flow
```

```bash
uip maestro flow format DependencySimFlow.flow
```

```bash
uip maestro flow validate DependencySimFlow.flow
```

**Check:** `"Status": "Valid"`, no `Warnings`.

### 9. Resources and pack

```bash
cd ..
```

```bash
uip solution resources refresh
```

**Check:** `Synced 0 resources (1 already in solution)`, plus two warnings that the function and the
Flow "were not checked for resource contributions". They're harmless: the bucket was declared in
step 7.

```bash
uip solution pack . --dry-run
```

**Check:** `"Status": "Valid"`.

**Look inside the package.** A real pack, to a folder outside the Solution, shows what reaches the
tenant:

```bash
uip solution pack . /tmp/dependency-pack --output json
```

```bash
unzip -q -o /tmp/dependency-pack/DependencySim_1.0.0.zip -d /tmp/dependency-pack/unzipped
```

```bash
unzip -l /tmp/dependency-pack/unzipped/files/*/DependencySim.Function.DependencySimFunction.1.0.0.nupkg | grep -E "wheels|uv.lock|pyproject"
```

**Check:** three lines: `content/pyproject.toml`, `content/uv.lock` and
`content/wheels/evsim_calc-1.0.0-py3-none-any.whl`. The library travels inside the function's
package, as the address-lookup jar travels inside Evelyn's zip.

## What you end up with

```
dependency-simulation/
├── data/calculations.csv                    the input: 10 rows, uploaded to the bucket on the tenant
├── evsim-calc/                              the library's own project
│   ├── pyproject.toml, uv.lock              version 1.0.0, build backend uv_build
│   ├── src/evsim_calc/__init__.py           calculate(), OPERANDS, __version__
│   ├── tests/test_calculate.py              18 tests
│   └── dist/evsim_calc-1.0.0-py3-none-any.whl   built by `uv build`, not committed
└── DependencySim/                           the Solution
    ├── DependencySim.uipx, resources/       tool-managed
    ├── DependencySimFunction/
    │   ├── wheels/evsim_calc-1.0.0-py3-none-any.whl   the library, as shipped
    │   ├── pyproject.toml, uv.lock          evsim-calc==1.0.0, pinned to that wheel
    │   ├── main.py, calculations.py, test_main.py
    │   └── bindings.json, entry-points.json, …        generated, plus the bucket entry
    └── DependencySimFlow/DependencySimFlow.flow       the source; the .bpmn is generated from it
```

## Expected result

A run with the default input, `csv_path` `input/calculations.csv`, returns `count` 10,
`library_version` `1.0.0`, and one `results` entry per row, in file order:

| `line` | `integer_1` | `integer_2` | `operand` | `result` |
|---|---|---|---|---|
| 2 | 12 | 30 | add | 42 |
| 3 | -5 | 8 | add | 3 |
| 4 | 100 | 58 | subtract | 42 |
| 5 | 3 | 10 | subtract | -7 |
| 6 | 7 | 6 | multiply | 42 |
| 7 | -4 | 25 | multiply | -100 |
| 8 | 84 | 4 | divide | 21 |
| 9 | -7 | 2 | divide | -3 |
| 10 | 7 | -2 | divide | -3 |
| 11 | 0 | 5 | divide | 0 |

`line` is the row's line in the CSV; line 1 is the header. The tests assert the same results.

## Run it

[HOW_TO_RUN.md](HOW_TO_RUN.md) runs this simulation in four levels: the tests, a local run, the
tenant run, and a deployed run started over HTTP with curl or Postman. It also says where to look in
the browser, and lists the things only the tenant run can confirm.

## Try this

1. **Release 1.1.0 with a new operand, `power`.** In `evsim-calc`: add the operand and a test, then
   `uv version 1.1.0` and `uv build --wheel`. In the function: delete the 1.0.0 wheel, copy the new
   one into `wheels/`, `uv add ./wheels/evsim_calc-1.1.0-py3-none-any.whl` and
   `uv add "evsim-calc==1.1.0"`. The tests that name 1.0.0 fail until you update them. That's
   Evelyn's version bump of `fircosoft-trust` from 4.3.0, at toy size: build, publish, change one
   version, re-lock.
2. **Change the library but keep the version.** Edit `calculate`, rebuild the 1.0.0 wheel and copy it
   over the old one. The next `uv run` refuses to start: `Hash mismatch for evsim-calc`, with the
   expected and the computed sha256. `uv lock` and even `uv lock --refresh-package evsim-calc` keep
   the old hash. Like a release repository in Nexus, a published version doesn't change: release
   1.0.1 instead. To accept the new file anyway, `uv lock --upgrade-package evsim-calc`.
3. **Depend on the source instead of the wheel.** In the function, `uv add ../../evsim-calc`. The
   function still runs locally, but `test_the_library_is_installed_from_the_vendored_wheel` and
   `test_uv_lock_pins_the_wheel_in_this_folder` fail: `uv.lock` now points at `../../evsim-calc`, a
   folder the function's package doesn't contain. On the tenant the install would fail
   (**Inference**). Undo with `uv add ./wheels/evsim_calc-1.0.0-py3-none-any.whl` and
   `uv add "evsim-calc==1.0.0"`.
4. **Fall into the trap.** In the library, make `divide` return `integer_1 // integer_2`. Two library
   tests fail. Rebuild, copy the wheel, `uv lock --upgrade-package evsim-calc`: the function's
   `test_the_ten_rows_give_the_expected_results` fails too, on lines 9 and 10. In a port, nothing
   but a test like that catches it.
5. **Java's int overflow.** Add `2147483647,1,add` to the CSV. Java's `int` wraps around to
   `-2147483648`; Python gives `2147483648`. Should the port match Java? That is a parity decision
   for the team, not a library bug.

## What building it taught

| Finding | Evidence | What was done |
|---|---|---|
| `uv init --lib` writes your git name and email into `authors` unless told not to, and they end up in the wheel's metadata | A first `uv init --lib` filled `authors` from `git config` | `--author-from none` in step 2 |
| `uv add <path to a .whl>` writes an unpinned dependency plus a `[tool.uv.sources]` path; a second `uv add "evsim-calc==1.0.0"` pins it and keeps the source | `pyproject.toml` after each command | Step 5 runs both |
| `uv.lock` records a path source and the wheel's sha256, with the path relative to the project | The lock's `evsim-calc` block | `test_uv_lock_pins_the_wheel_in_this_folder` |
| `uv build` wheels are reproducible: same source, same bytes | Two builds in different folders gave the same sha256 | The hash in your lock is stable across rebuilds with the same `uv` |
| `uv` refuses a different file under a version it has locked: `Hash mismatch`. `uv lock` and `--refresh-package` keep the old hash; `uv lock --upgrade-package evsim-calc` takes the new one | A changed 1.0.0 wheel copied over the old one ([Try this](#try-this) 2) | A changed library gets a new version |
| `uip solution pack` ships everything in the function folder: the wheel, `uv.lock`, `pyproject.toml`, also `.env` and the tests | A real pack, unzipped: `content/wheels/…whl`, `content/uv.lock` | Step 9 shows it. Keep secrets out of the folder |
| The SDK's own packer, `uipath pack`, is stricter: by default it packs only `.py`, `.json`, `.yaml`, `.yml`, `.md` and `.mermaid` files, and needs `packOptions` in `uipath.json` for anything else, such as a `.whl` | The `uipath` 2.14.27 source, `_cli/_utils/_project_files.py` | This example packs with `uip solution pack` only |
| The function package's `operate.json` has `"dependencies": null` | The unzipped package | Dependencies come from `pyproject.toml` and `uv.lock` alone (**Inference**) |
| Every function package carries its own copy of the library | Each function is packed from its own folder | Two functions using `evsim-calc` would each vendor the wheel, as two WorkFusion workers each bundle their jar |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Fewer than `18 passed` in `evsim-calc` | The library changed | Read the failing test's name |
| `uv run` fails: `Hash mismatch for evsim-calc` | A different wheel was copied into `wheels/` under the same version | Copy back the wheel the lock expects, or release a new version. To accept the new file: `uv lock --upgrade-package evsim-calc` |
| `test_uv_lock_pins_the_wheel_in_this_folder` fails | `uv.lock` points somewhere other than `wheels/evsim_calc-1.0.0-py3-none-any.whl` | Step 5's two `uv add` commands |
| `test_the_library_is_installed_from_the_vendored_wheel` fails | The dependency points at the source (`../../evsim-calc`) or another path | Step 5's two `uv add` commands |
| `uv add ./wheels/…` fails: `Distribution not found` | The wheel isn't in `wheels/` yet, or the name is mistyped | `ls wheels/`, then step 5 again |
| `ModuleNotFoundError: No module named 'evsim_calc'` | Run outside the function's `.venv` | Run with `uv run` from the function folder |
| `Line 9: … division by zero`, `unknown operand` | A bad row in the CSV | Fix the row the message names |
| `echo $FN` prints nothing | New terminal, or the function isn't in the Solution | Step 7, then 8b |
| `validate`: `MISSING_OUTPUT_MAPPING` | 8f not done | Do it |
| Node IDs end in `2` | A node added twice | Start again from step 1 in an empty folder |
| The package listing in step 9 has no `wheels/` | The wheel was outside the function folder when you packed | Step 5 |

## Done when

- [ ] `uv run pytest -q` passes in `evsim-calc` (18) and in the function (10).
- [ ] The local run (step 6) prints the ten results, with `-7 divide 2 = -3`, and `evsim-calc 1.0.0`.
- [ ] The Flow `validate`s as Valid with no warnings, and `uip solution pack . --dry-run` is Valid.
- [ ] The function's package lists `content/wheels/evsim_calc-1.0.0-py3-none-any.whl` and
  `content/uv.lock` (step 9).
- [ ] You can say where the library's version is declared, where it's pinned, and why the wheel
  is inside the function folder.
- [ ] **[On the tenant](HOW_TO_RUN.md#3-on-the-tenant):** the second debug run returns `count` 10 and
  `library_version` `1.0.0`, and you've noted which rows of
  [Things only the tenant run can confirm](HOW_TO_RUN.md#things-only-the-tenant-run-can-confirm)
  turned out true.
