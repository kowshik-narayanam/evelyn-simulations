# Evelyn simulations: instructions for AI agents

This repo holds small UiPath simulations of pieces of Evelyn, WorkFusion's Names Sanctions
Screening digital worker. The human overview is [README.md](README.md). Each simulation folder has
its own README.md and AGENTS.md; for files inside a folder, its AGENTS.md wins over this one. This
file covers the repo as a whole and how to add the next simulation.

## First: find the Evelyn source

A simulation is only as good as what it copies. Before you design or change one, ask the user for
the paths to their local checkouts of these two repos, and ask them to pull the latest. They are
private, so the user pulls; you don't.

| Repo | What it is | Clone from (team access needed) | It's the right folder if it has |
|---|---|---|---|
| `names-screening` | Evelyn's code: Java task processors, business processes, configuration | `git@bitbucket.org:work-fusion/names-screening.git` | `pom.xml`, `names-screening-jnw/`, `names-screening-package/` |
| `nss-classification-model` | Evelyn's names classification model (Python) | `git@bitbucket.org:work-fusion/nss-classification-model.git` | `model.yml`, `nss_model/` |

1. Check each path the user gives against the last column.
2. Note each repo's branch and commit (`git -C <path> log -1 --format='%h %ad' --date=short`). Put
   them in the simulation's README as the snapshot it was built against.
3. **If a repo is missing**, or the folder lacks those markers, warn the user plainly: "I couldn't
   locate `<repo>`, so I don't have enough information about Evelyn's code for this piece."
   Continue only if they agree. Then mark every claim about Evelyn **Inference**, and say in the
   simulation's README which repo was missing.
4. **Read only.** Never edit, commit or push in those repos. Don't copy their code, configuration,
   test data or credentials into this repo, because this repo may be public. Describe the behaviour
   in your own words, and cite class names and `path:line`.

## Layout

```
README.md, AGENTS.md, CLAUDE.md, .gitignore   this repo
<Component> Simulation/                       one folder per simulation, e.g. CsvProcessor Simulation
├── README.md                                 the human guide: rebuild, expected result, try this
├── HOW_TO_RUN.md                             running it: tests, local run, tenant run
├── AGENTS.md, CLAUDE.md                      rules for that folder (CLAUDE.md holds "@AGENTS.md")
├── data/                                     mock input
└── <Solution>/                               the UiPath Solution: function projects and Flows
```

## Adding the next simulation

1. **Agree the scope with the user:** which Evelyn piece, which behaviour the toy version keeps,
   and what it drops.
2. **Find that piece** in `names-screening` (and in the model, if it's involved). Cite `path:line`.
3. **Build it in a new root folder**, `<Component> Simulation`. The usual shape: one Solution
   (`uip solution init`), Python coded function projects (`uv`, a pinned `uipath` version), Maestro
   Flows built with `uip maestro flow` commands, and mock data in `data/`. Reuse what the existing
   simulations already show instead of inventing a second way:
   [CsvProcessor Simulation](CsvProcessor%20Simulation/README.md) for a Flow calling a Flow and a
   shared contract, [Configuration Simulation](Configuration%20Simulation/README.md) for settings,
   a Switch over providers and secrets in assets, [Dependency Simulation](Dependency%20Simulation/README.md)
   for a library shipped inside a function as a wheel, [Datastore Simulation](Datastore%20Simulation/README.md)
   for Data Fabric entities with a primary key and a foreign key.
4. **Write the README** with the same sections as CsvProcessor Simulation:
   - the point of it;
   - an Evelyn → here table, and a WorkFusion → UiPath table;
   - the status: what was verified locally and what wasn't run;
   - "Build it yourself": every command, one per block, with a **Check** after each step;
   - the expected result, a "Run it" pointer to HOW_TO_RUN.md, try this, troubleshooting, done
     when.

   Then **write HOW_TO_RUN.md**, with the same sections as CsvProcessor Simulation's: get it,
   tests, a local run, on the tenant (a check after each step), deployed and started over HTTP
   (curl and Postman, untested until someone runs it), where to look in the browser,
   things only the tenant run can confirm, and when a run fails. Running belongs there, not in the
   README.
5. **Mock data only.** Use placeholder names (Alice and Bob, John Doe, Foo Bar, Lorem Ipsum) or tech
   names with their first letters swapped (Gill Bates, Melon Eusk). Design the data so a wrong
   implementation fails a test.
6. **Leave a runnable test** in each function project (`uv run pytest -q`), and put the expected
   count in the README.
7. **Verify** by running the README's commands as written in an empty folder. Record what passed.
8. **List it** with a new row in the Simulations table in [README.md](README.md).

## Rules

1. **Nothing on a tenant without the user's go-ahead.** That covers `uip maestro flow debug`,
   `uip solution upload` / `publish` / `deploy` and bucket writes. Read-only calls (`validate`,
   `registry`, `resources list`, `resources refresh`) are fine.
2. **No secrets.** Never run `uipath auth` in a project folder (it writes a token into `.env`, and
   `pack` ships `.env`). Never commit `.env`.
3. **Don't commit or push** unless the user asks.
4. **Unique UiPath names.** Function, Flow and bucket names are tenant-wide. Don't reuse another
   simulation's.
5. **Say which file is the source.** The `.flow` is the source, and the `.bpmn` is generated from
   it. `entry-points.json`, `uv.lock`, `.uipx` and `resources/` are tool-managed.
6. **Label guesses.** Anything not verified locally or on a tenant is marked **Inference**.
