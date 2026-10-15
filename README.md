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
| [CsvProcessor Simulation](CsvProcessor%20Simulation/README.md) | CSV ingestion: `CsvTaskProcessor` and `CsvSchemaProducerProcessor`, and the CSV BP calling the main BP | A Flow calling a Flow, a contract shared by two function projects, a storage bucket | Verified locally; not run on a tenant yet |

Each folder stands on its own. Its README has the build commands from an empty folder, the
expected result and the troubleshooting. Start there.

## What you need

| Tool | For |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | Python 3.11 projects and their tests |
| The `uip` CLI, logged in (`uip login status`) | Solution and Flow commands |
| `jq` | The JSON edits in the build steps |
| A UiPath tenant | Only the "Run it on the tenant" steps |

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
