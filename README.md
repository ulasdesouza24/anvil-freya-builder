# Anvil Freya builder

A builder for the Freya × YC "Build the Builder" hackathon. It reads a bank's brief and the brief's tool API file, and
creates a phone agent as a Freya workflow. One command, no manual step.

The builder runs Claude through the Claude Agent SDK, with the skill `build-freya-agent` and tested helpers. The
methods come from Anvil, an agentic system that builds, tests and evolves agents:

- every rule of the brief goes into a numbered rule ledger, and a coverage check at the end maps each rule to a node,
  a route, a tool or code;
- dates and numbers (business days, deadlines, windows, floors, attempt counts) are computed by code steps that run
  locally before they go to the platform, never by the model;
- tools come from the OpenAPI file, with hooks that normalize model-filled values and tell the model what a result
  means (`what_to_do_next`), and a close guard that sets the outcome from the tool results;
- static checks catch the faults that the platform drops without an error, then a dry run, a chat test, and the
  practice customers when the brief has them.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`kit/` holds the public files of the hackathon kit (v3: docs, `freya.py`, the practice runner and customers, the
example agent). `sh setup_kit.sh <unzipped kit>` copies a newer kit version over it.

Set the environment (the kit's `env.example`): `FREYA_API_KEY`, `FREYA_API_URL`, `FREYA_BANK_TEAM_KEY`. On a
python.org build of Python on macOS, also set `SSL_CERT_FILE="$(python -c 'import certifi; print(certifi.where())')"`.
The builder needs a Claude login (or `ANTHROPIC_API_KEY`).

## Run

```bash
python3 build.py {brief_path} {tool_api_path}
python3 build.py <brief.md> [<more briefs>] <tool API file.json> [--slot <name>] [--test A|B|none] [--minutes 28]
```

- A later brief builds on the earlier ones: pass them in order.
- `--test` names the practice customers of the kit to test on. Use `none` for a brief without practice customers.
- The time budget includes the tests. The default is 28 minutes.

Output:

| Path | What it is |
|---|---|
| `submission/<slot>.workflow.json` | The exported phone agent (`freya.export_workflow`), the file to submit |
| `submission/<slot>.trace.log` | The trace: start and end, each model call with its model and purpose, what was created on Freya (workflow id, agent id, number of steps and tools), each test. Key values are removed |
| `traces/<start>-<slot>.log` | The same trace, kept for each run |
| `traces/<start>-<slot>.jsonl` | Every message of the run |
| `work/<slot>/` | The rule ledger, the design, the generator, the coverage, the test results |

## Layout

| Path | What it is |
|---|---|
| `build.py` | The command: inputs, time budget, trace, export |
| `.claude/skills/build-freya-agent/SKILL.md` | The steps of the builder |
| `reference/patterns.md` | What worked and what failed on the platform, as general patterns |
| `lib/` | Helpers: tools from OpenAPI, code steps, static checks, call analysis, chat |
| `rehearsal/` | Practice material that we wrote (a raw-material version of a public brief) |
