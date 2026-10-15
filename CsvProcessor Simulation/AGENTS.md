# Student sections: instructions for AI agents

Read this before you change anything in this folder. The human guide, with the spec, the build
commands and the expected result, is [README.md](README.md).

## What this example is

Two Maestro Flows in one Solution, one calling the other. It is the UiPath form of a WorkFusion
BP → BP call (`BP_CALL` with `sendResultToCaller`).
- `StudentIntakeFlow` parses `input/students.csv` from the bucket `StudentSectionsFiles` into
  `Student` objects.
- It calls `StudentSectionsFlow` through a Flow-calls-Flow node (`uipath.core.flow.<key>`,
  `fireAndForget: false`).
- `StudentSectionsFlow` sorts the students by first name, splits them 10 / 10 and writes
  `output/section-1.csv` and `output/section-2.csv` back to the bucket.

## Source vs generated

| Edit these | Never edit these (regenerate instead) |
|---|---|
| `StudentSections/*Function/{main.py, intake.py, sections.py, student_contract.py, test_main.py}` | `entry-points.json`, `main.mermaid`, `project.uiproj`, `.agent/`, `.claude/`, `.uipath/`, `uv.lock` (run `uv run uipath init` / `uv lock`) |
| `StudentSections/*Flow/*.flow`, **only by re-running the README's commands** | `StudentSections.uipx`, `resources/` (managed by `uip solution …`) |
| The bucket entry in each `bindings.json` (README step 6) | `operate.json`, any `.bpmn` (generated from the `.flow`) |
| `data/students.csv`, README, notes | `StudentSections/AGENTS.md`, `CLAUDE.md` and those inside each function: CLI boilerplate, not this file |

## Rules

1. **Nothing on the tenant without the user's go-ahead.** That includes `uip maestro flow debug`,
   `uip solution upload` / `publish` / `deploy`, and `uip or buckets create` / `bucket-files upload`.
   Read-only calls (`validate`, `registry`, `resources refresh`, `resources list`) are fine.
2. **Never run `uipath auth`** in a project folder. It writes a token into `.env`, and
   `uip solution pack` ships `.env`. Use `uip login`.
3. **`student_contract.py` exists twice and must stay byte-identical.** Each function is packaged
   alone, so neither can import from the other. Edit one copy, then copy it over the other.
   `test_the_two_contract_copies_are_identical` enforces this.
4. **Keep `data/students.csv` jumbled.** `test_the_input_file_is_jumbled` fails if it is reordered.
   Change the expected sections in the tests and the README together if you change the data.
5. **The `.flow` files are built by commands.** If you change a Flow, change the README's commands,
   rebuild in an empty `/tmp` folder, and commit what the commands produce. The only hand edits are
   the End-node outputs (8f, 9f) and the bucket bindings (step 6), each shown with a `jq` command.
6. **Build the child Flow before the parent.** The parent's Flow node takes its inputs from the
   child's `in` variables.
7. **Names are tenant-wide.** Don't reuse `StudentIntakeFunction`, `StudentSectionsFunction`, the two
   Flow names or the bucket name in another project on the same tenant.
8. **Label guesses.** Anything not verified locally or on the tenant is marked **Inference** or
   listed under "Things only the tenant run can confirm".

## Verify after any change

Run from `StudentSections/`:

| Check | Command | Expect |
|---|---|---|
| Intake tests | `cd StudentIntakeFunction && uv run pytest -q` | `7 passed` |
| Sections tests | `cd StudentSectionsFunction && uv run pytest -q` | `9 passed` |
| Child Flow | `uip maestro flow validate StudentSectionsFlow/StudentSectionsFlow.flow` | `Valid`, no `Warnings` |
| Parent Flow | `uip maestro flow validate StudentIntakeFlow/StudentIntakeFlow.flow` | `Valid`, no `Warnings` |
| Solution | `uip solution pack . --dry-run` | `Valid` |
| README | every `bash` block of steps 1–10, as written, in an empty `/tmp` folder | Exit 0; `.flow` files equal to the committed ones apart from keys |
