# Evelyn simulations

Small UiPath versions of pieces of **Evelyn**, WorkFusion's Names Sanctions Screening digital
worker. Each simulation copies one Evelyn behaviour at toy size, with mock data, so the Evelyn
team can try the UiPath building blocks (Maestro Flows, Python coded functions, storage buckets)
before the real port.

**Why this exists:** Evelyn is moving from WorkFusion to UiPath. A simulation shows the UiPath
shape of one Evelyn piece without touching Evelyn's code, its data or a shared tenant. When the
port starts, each simulation is a worked example of one piece.

## Simulations

| Folder | Evelyn piece it simulates | UiPath pieces it shows | Status |
|---|---|---|---|
| [CsvProcessor Simulation](CsvProcessor%20Simulation/README.md) ([run it](CsvProcessor%20Simulation/HOW_TO_RUN.md)) | CSV ingestion: `CsvTaskProcessor` and `CsvSchemaProducerProcessor`, and the CSV BP calling the main BP | A Flow calling a Flow, a contract shared by two function projects, a storage bucket | Verified locally; not run on a tenant yet |
| [Configuration Simulation](Configuration%20Simulation/README.md) ([run it](Configuration%20Simulation/HOW_TO_RUN.md)) | The configuration: `configuration.json` (the form), the saved values, `INPUT_TYPE`, and `PROVIDER_ID` picking a provider | Settings loaded once per run in three layers, a Switch with one node per provider, an `inout` global, a Credential asset for the secret | Verified locally; not run on a tenant yet |
| [Dependency Simulation](Dependency%20Simulation/README.md) ([run it](Dependency%20Simulation/HOW_TO_RUN.md)) | Shipping a library: the `fircosoft-trust` and `address-lookup-jnw` jars, declared in a `pom.xml` and bundled into Evelyn's package | A library in its own project, built into a wheel, vendored inside a coded function, pinned in `pyproject.toml` and `uv.lock` | Verified locally; not run on a tenant yet |
| [Datastore Simulation](Datastore%20Simulation/README.md) ([run it](Datastore%20Simulation/HOW_TO_RUN.md)) | Two related datastore tables: `alert_analytics` and `hit_analytics`, one alert with zero or many hits, linked by a text column with no foreign key | Two Data Fabric entities, customers and orders: a primary key, a unique business key, a `RELATIONSHIP` foreign key, a lookup before insert, a LEFT JOIN | Verified locally; not run on a tenant yet |

Each folder stands on its own, with two guides:
- **HOW_TO_RUN.md** runs what's there: the tests, a local run, the tenant run, then a deployed
  run started with curl or Postman. It also says where to find the run, the bucket and the asset
  in the browser. Start here to see it work.
- **README.md** explains what it simulates, and builds it from an empty folder by commands. It
  also has the expected result and the troubleshooting.

## What you need

| Tool | For |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | Python 3.11 projects and their tests |
| The `uip` CLI, logged in (`uip login status`) | Solution and Flow commands |
| `jq` | The JSON edits in the build steps |
| `unzip` | Looking inside a package (Dependency Simulation) |
| A UiPath tenant | Only levels 3 and 4 of each HOW_TO_RUN.md |
| `curl`, or [Postman](https://www.postman.com/) | Level 4: starting a deployed Flow over HTTP |

## Ground rules

- **Mock data only.** No real people, no customer data, no secrets. Names are placeholders such as
  Alice and Bob, John Doe and Foo Bar, or tech names with their first letters swapped (Gill Bates).
- **No tokens in git.** `.gitignore` keeps `.env`, `.venv/` and caches out. Never run `uipath auth`
  inside a project folder: it writes a token into `.env`, and `uip solution pack` ships `.env`.
  Use `uip login`.
- **Rebuildable.** Each README rebuilds its simulation from an empty folder by commands and says
  what has and hasn't been verified.
- **Unique names.** UiPath names are tenant-wide, so each simulation uses its own function, Flow
  and bucket names.

## Working with an AI assistant

[AGENTS.md](AGENTS.md) (and [CLAUDE.md](CLAUDE.md), which loads it) tells an AI assistant how this
repo is laid out and how to add the next simulation. Before it designs anything, it asks for your
local checkouts of Evelyn's code and its names classification model, and warns you if it can't
find them.
