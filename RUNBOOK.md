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
3. The slot name comes from the brief file name (`hidden-1`, `hidden-2`). Never reuse `brief-a` or `brief-b`.

## Run the builder (once for each brief)

```bash
python3 build.py ~/Desktop/freya-final/hidden-1.md ~/Desktop/freya-final/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.console.log
```

The slot is the name of the brief file (`hidden-1`). The default is `--test none` and 28 minutes.

- `--test none`: the bank mock has no practice customers for a hidden brief.
- Run the briefs one after the other, not at the same time: they share the Claude login and the simulation queue.
- Watch the console. A run ends with a `created ... steps=N tools=M` line and an `export submission/hidden-1.workflow.json` line.

## After each run

1. Check that `submission/<slot>.workflow.json` exists and that `submission/<slot>.trace.log` has a `start` and an
   `end` line, and no key value (`grep -c fak_ submission/*.log` gives 0).
2. Run the static check: `python lib/check_workflow.py submission/<slot>.workflow.json --openapi <tool API file>`. It
   must give 0 errors.
3. Talk to the agent once: `python lib/chat.py <workflow_id> --vars '<call variables of the brief>' "Hello?"`. The first
   line must follow the brief's opening rule.
4. If the run crashed or the export is missing: find the cause in the trace, fix only the crash in the builder
   (commit it with a message that says it is a crash fix), and run the builder again on that brief.

## When the platform is down or slow

Seen on Saturday 2026-10-10 from 16:50 to 17:10 Istanbul time: chat gave 503, and for some minutes after, a tool call
took 6 to 11 seconds and simulations hung.

1. Check with `python lib/platform_check.py <workflow_id>`. Wait at least 2 minutes between two checks.
2. The builder does not change a workflow on an outage test, and it publishes the best tested version. A run without
   any test publishes its first checked draft.
3. A test that you stop on your side keeps running on Freya until it ends, and the next test waits for it. Do not
   stop a test unless the run is lost anyway.
4. When the platform is up again and time is left, run the builder once more on the brief. Submit the run with the
   better test result, with the trace of that run.

## Submit (before 20:00 UTC)

1. Commit `submission/` (the two workflows and the two traces) and push to GitHub.
2. Send the form to the address in the kit e-mail:

   ```json
   {
     "team": "<team name>",
     "repo": "https://github.com/<owner>/anvil-freya-builder",
     "commit": "<the commit of the builder that made the runs>",
     "run_command": "python3 build.py {brief_path} {tool_api_path}",
     "workflows": { "hidden-1": "submission/hidden-1.workflow.json", "hidden-2": "submission/hidden-2.workflow.json" },
     "traces": { "hidden-1": "submission/hidden-1.trace.log", "hidden-2": "submission/hidden-2.trace.log" }
   }
   ```

3. The top ten teams get their repository cloned and the builder run again. Freya needs read access to the repository.

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
