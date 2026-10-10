# Runbook: the final (Sunday 2026-10-11)

Hidden briefs open at 17:00 UTC (20:00 Istanbul). Submissions close at 20:00 UTC (23:00 Istanbul). Each hidden brief
comes with its own tool API file. Freya sends the submission steps by e-mail before 17:00 UTC.

## Rules to keep (from the kit README)

- Run the builder on each brief with no manual step. Do not edit a phone agent by hand.
- Do not write anything from a hidden brief into the builder: no rule, no value, no name. A fix of a crash (for
  example a table that the parser did not expect) is allowed.
- One builder run on one brief takes 30 minutes at most, tests included.
- You may run the builder more than once, and submit the phone agent of one run with the trace of that run.
- Submit for each brief: the exported workflow file, the trace of the run, and the builder code.

## Before 17:00 UTC

1. Read the submission e-mail. Write down what to submit and where.
2. Open a terminal in the builder folder and set the environment:

   ```bash
   cd ~/Desktop/anvil-freya-builder
   source ~/Desktop/freya-kit/build-the-builder/env.sh
   unset ANTHROPIC_API_KEY
   ```

3. Check the connection: `python -c "import sys; sys.path.insert(0,'kit'); import freya; print(freya.workspace_id())"`.
4. Check the Claude login: `claude -p "say ok"` must print an answer.
5. Make sure that no simulation runs in the workspace (one runs at a time).
6. Commit the builder. The commit at 17:00 UTC is the frozen builder: after it, only crash fixes.

## At 17:00 UTC

1. Download the hidden briefs and their tool API files into `~/Desktop/freya-final/` (outside the builder folder).
2. Read the first lines of each brief. Note if a brief builds on another one: then pass both, in order.
3. Pick a slot name for each brief, for example `final-1` and `final-2`. Never reuse `brief-a` or `brief-b`.

## Run the builder (once for each brief)

```bash
python build.py ~/Desktop/freya-final/<brief>.md --openapi ~/Desktop/freya-final/<tool API file> --slot final-1 --test none --minutes 28
```

- `--test none`: the bank mock has no practice customers for a hidden brief.
- Run the briefs one after the other, not at the same time: they share the Claude login and the simulation queue.
- Watch `traces/<start>-final-1.log`. A run ends with a line `export ... -> out/final-1.workflow.json`.

## After each run

1. Check that `out/<slot>.workflow.json` exists and that the trace has a `start` and an `end` line.
2. Run the static check: `python lib/check_workflow.py out/<slot>.workflow.json --openapi <tool API file>`. It must
   give 0 errors.
3. Talk to the agent once: `python lib/chat.py <workflow_id> --vars '<call variables of the brief>' "Hello?"`. The first
   line must follow the brief's opening rule.
4. If the run crashed or the export is missing: find the cause in the trace, fix only the crash in the builder
   (commit it with a message that says it is a crash fix), and run the builder again on that brief.

## Submit (before 20:00 UTC)

For each brief: `out/<slot>.workflow.json`, `traces/<start>-<slot>.log` (and the `.jsonl` next to it), and the builder
code (this repository, with the commit that made the run). Follow the e-mail for the format.

## Time plan

| UTC | What |
|---|---|
| 17:00 | Download, read, slot names |
| 17:10 | Builder run 1 (up to 30 minutes) |
| 17:45 | Checks of run 1, builder run 2 |
| 18:20 | Checks of run 2 |
| 18:30 | Optional second runs, if a run was weak or crashed |
| 19:30 | Submit everything |
| 20:00 | Close |
