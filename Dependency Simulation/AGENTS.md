# Dependency simulation: instructions for AI agents

Read this before you change anything in this folder. The human guide, with the build commands and
the expected result, is [README.md](README.md); running it is [HOW_TO_RUN.md](HOW_TO_RUN.md).

## What this example is

A library shipped inside a coded function, the way Evelyn bundles the `fircosoft-trust` and
`address-lookup-jnw` jars.
- `evsim-calc/` is the library's own project: `calculate(integer_1, integer_2, operand)` returns an
  integer; `divide` truncates toward zero, as Java's `int` division does.
- `uv build --wheel` makes `evsim_calc-1.0.0-py3-none-any.whl`. A copy lives in
  `DependencySim/DependencySimFunction/wheels/`, and the function's `pyproject.toml` (with
  `[tool.uv.sources]`) and `uv.lock` pin it.
- `DependencySimFlow` has one node, **Calculate**: it reads `input/calculations.csv` from the bucket
  `DependencySimFiles` and calls the library once per row.

## Source vs generated

| Edit these | Never edit these (regenerate instead) |
|---|---|
| `evsim-calc/src/evsim_calc/__init__.py`, `evsim-calc/tests/test_calculate.py` | `evsim-calc/uv.lock`, `evsim-calc/dist/` (run `uv lock`, `uv build --wheel`) |
| `DependencySim/DependencySimFunction/{main.py, calculations.py, test_main.py}` | `entry-points.json`, `main.mermaid`, `project.uiproj`, `.agent/`, `.claude/`, `.uipath/`, `uv.lock` (run `uv run uipath init` / `uv lock`) |
| `DependencySim/DependencySimFlow/DependencySimFlow.flow`, **only by re-running the README's commands** | `DependencySim.uipx`, `resources/` (managed by `uip solution …`) |
| The bucket entry in `bindings.json` (README step 6) | `operate.json`, any `.bpmn` (generated from the `.flow`) |
| `data/`, README, HOW_TO_RUN | `wheels/*.whl`: only ever a copy of a wheel `uv build` made (see rule 3) |

## Rules

1. **Nothing on the tenant without the user's go-ahead.** That includes `uip maestro flow debug`,
   `uip solution upload` / `publish` / `deploy` and bucket uploads. Read-only calls (`validate`,
   `registry`, `resources refresh`, `resources list`, `pack`) are fine.
2. **No secrets.** Never run `uipath auth` in the function folder: it writes a token into `.env`, and
   `pack` ships every file in the folder, `.env` included.
3. **A changed library is a new version.** Change `evsim-calc`, then `uv version <new>`, `uv build
   --wheel`, replace the wheel in `wheels/`, `uv add ./wheels/<new wheel>` and
   `uv add "evsim-calc==<new>"`. Update the tests and the README that name the version. Never copy a
   different file over a released version's wheel: `uv` refuses it (`Hash mismatch`), and so would
   anyone who locked the old one.
4. **The wheel stays inside the function folder.** Never make the function depend on
   `../../evsim-calc` or any path outside its folder: `pack` ships only the function's folder, and
   `test_the_library_is_installed_from_the_vendored_wheel` fails.
5. **Keep the name unpublished.** `evsim-calc` isn't on PyPI. Don't rename the library to a name that
   is, or a robot that ever looks it up there installs a stranger's package.
6. **Keep the data's trap.** Rows `-7,2,divide` and `7,-2,divide` are what catch Python's `//`.
   Change `EXPECTED` in `test_main.py`, the README's tables and HOW_TO_RUN's checks together if you
   change `data/`.
7. **The `.flow` is built by commands.** If you change it, change the README's commands, rebuild in
   an empty folder, and keep what the commands produce. The only hand edit is the End outputs (8f),
   shown with a `jq` command.
8. **Names are tenant-wide.** Don't reuse `DependencySimFunction`, `DependencySimFlow` or
   `DependencySimFiles` in another simulation.
9. **Label guesses.** Anything not verified locally or on the tenant is marked **Inference** or listed
   under "Things only the tenant run can confirm" in HOW_TO_RUN.md.

## Verify after any change

| Check | Run from | Command | Expect |
|---|---|---|---|
| Library tests | `evsim-calc/` | `uv run pytest -q` | `18 passed` |
| Function tests | `DependencySim/DependencySimFunction/` | `uv run pytest -q` | `10 passed` |
| Flow | `DependencySim/` | `uip maestro flow validate DependencySimFlow/DependencySimFlow.flow` | `Valid`, no `Warnings` |
| Solution | `DependencySim/` | `uip solution pack . --dry-run` | `Valid` |
| The wheel ships | `DependencySim/` | HOW_TO_RUN level 2, "The wheel inside the package" | `content/wheels/evsim_calc-1.0.0-py3-none-any.whl` and `content/uv.lock` |
| README | an empty folder | every `bash` block of steps 1–9, as written | Exit 0; the `.flow` equal to this one apart from keys |
