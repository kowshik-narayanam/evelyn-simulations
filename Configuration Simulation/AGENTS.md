# Configuration simulation: instructions for AI agents

Read this before you change anything in this folder. The human guide, with the build commands and
the expected result, is [README.md](README.md).

## What this example is

One Maestro Flow whose path is chosen by its configuration, the way Evelyn's `PROVIDER_ID` picks a
screening provider.
- **Load configuration** merges three layers: the form's defaults (`configuration.json`, inside the
  function), the saved payload (`config/configuration_payload.json` in the bucket
  `CalcConfigFiles`) and the run's `overrides`. It checks every value against the form.
- **Read numbers** reads `input/numbers.csv` (`INPUT_TYPE` CSV) or takes the trigger's `numbers`
  (API).
- The Switch **Which calculator?** sends the run to one of four calculator nodes, by `PROVIDER_ID`.
  Each checks the Credential asset `CalcApiKey`, calculates, and writes its output into the
  `inout` global `calculation`.
- **CSV report on?** decides whether **Write report** uploads the report.

## Source vs generated

| Edit these | Never edit these (regenerate instead) |
|---|---|
| `CalcConfig/CalcConfigFunction/{configuration.json, settings.py, calculator.py, main.py, test_main.py}` | `entry-points.json`, `main.mermaid`, `project.uiproj`, `.agent/`, `.claude/`, `.uipath/`, `uv.lock` (run `uv run uipath init` / `uv lock`) |
| `CalcConfig/CalcConfigFlow/CalcConfigFlow.flow`, **only by re-running the README's commands** | `CalcConfig.uipx`, `resources/` (managed by `uip solution …`) |
| The two entries in `bindings.json` (README step 5) | `operate.json`, any `.bpmn` (generated from the `.flow`) |
| `data/`, README, HOW_TO_RUN | `CalcConfig/AGENTS.md`, `CLAUDE.md` and those inside the function: CLI boilerplate, not this file |

## Rules

1. **Nothing on the tenant without the user's go-ahead.** That includes `uip maestro flow debug`,
   `uip solution upload` / `publish` / `deploy`, bucket uploads and `uip or assets create` /
   `update`. Read-only calls (`validate`, `registry`, `resources refresh`, `resources list`) are fine.
2. **No secrets anywhere in this folder.** The configuration names the Credential asset; it never
   holds the key. No node outputs or logs the key. Never run `uipath auth` in the function folder
   (it writes a token into `.env`, and `pack` ships `.env`).
3. **`configuration.json` is the one list of settings.** A new setting is a new field there, with a
   test. Don't add a setting in code that the form doesn't list: `load` rejects unknown keys.
4. **A new calculator touches seven places:** the form's `PROVIDER_ID` values, `OPERATORS` in
   `calculator.py`, `OPERATIONS` in `main.py`, a Switch case, a node, two edges and a variable update
   in the Flow, plus `EXPECTED`/`ALERTS` in the tests and the README. Do all of them or none.
5. **Keep the data's traps.** N-04 (rounding), N-05 (division by zero) and N-07 (exactly on the
   threshold) are what make the tests catch wrong rules. Change the README's tables, HOW_TO_RUN's checks
   and the tests' `EXPECTED` together if you change `data/`.
6. **The `.flow` is built by commands.** If you change it, change the README's commands, rebuild in
   an empty folder, and keep what the commands produce. The only hand edits are the variable updates
   (7f) and the End outputs (7g), each shown with a `jq` command.
7. **Names are tenant-wide.** Don't reuse `CalcConfigFunction`, `CalcConfigFlow`, `CalcConfigFiles` or
   `CalcApiKey` in another simulation.
8. **Label guesses.** Anything not verified locally or on the tenant is marked **Inference** or
   listed under "Things only the tenant run can confirm" in HOW_TO_RUN.md.

## Verify after any change

Run from `CalcConfig/`:

| Check | Command | Expect |
|---|---|---|
| Tests | `cd CalcConfigFunction && uv run pytest -q` | `32 passed` |
| Flow | `uip maestro flow validate CalcConfigFlow/CalcConfigFlow.flow` | `Valid`, no `Warnings` |
| Solution | `uip solution pack . --dry-run` | `Valid` |
| README | every `bash` block of steps 1–8, as written, in an empty folder | Exit 0 (except the deliberate typo in step 5); the `.flow` equal to this one apart from keys |
