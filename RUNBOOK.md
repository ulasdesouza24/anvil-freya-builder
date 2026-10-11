# Runbook: the final (Sunday 2026-10-11)

The final is ONE new case (the organisers, 2026-10-11): one brief with its own tool API file, and three hours. It
opens at 17:00 UTC (20:00 Istanbul) and submissions close at 20:00 UTC (23:00 Istanbul). Freya sends the submission
steps by e-mail before 17:00 UTC.

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
5. Make sure that no simulation runs in the workspace: `python lib/sim_queue.py` must say "no simulation runs".
6. Remove the practice and rehearsal files from `submission/`: `git rm -q submission/brief-* ; rm -f submission/rh-*`.
   The final commit must hold only the files of the hidden briefs.
7. Commit the builder. The commit at 17:00 UTC is the frozen builder: after it, only crash fixes.
8. Start the trace screen: `python3 lib/dashboard.py`, then open http://localhost:8765.

## At 17:00 UTC

1. Download the hidden briefs and their tool API files into `~/Desktop/freya-final/` (outside the builder folder).
2. Read the first lines of each brief. Note if a brief builds on another one: then pass both, in order.
3. The slot name comes from the brief file name (`hidden-1`, `hidden-2`). Never reuse `brief-a` or `brief-b`.

## Run the builder (four runs of the one brief)

The same builder gives drafts of different quality: without tests, raw Brief A scored 7, 8, 4, 7 and 1 of 10. So
run the builder four times on the brief and submit the best run. The rules allow this: "You may run it more than
once and submit the phone agent of one run, with that run's trace."

Give each run its own slot: `hidden-r1` to `hidden-r4`. If the brief builds on an earlier brief, pass both briefs,
in order.

```bash
python3 build.py ~/Desktop/freya-final/hidden.md ~/Desktop/freya-final/hidden.openapi.json --slot hidden-r1 2>&1 | tee traces/hidden-r1.console.log
```

The default is `--test none` and 28 minutes.

- `--test none`: the bank mock has no practice customers for the hidden brief.
- Run one build at a time: the builds share the Claude login.
- Watch the console. A run ends with a `created ... steps=N tools=M` line and an `export submission/<slot>.workflow.json` line.
- During each run, check the run before it (see "After each run" and "Choose the run to submit").

## Choose the run to submit

1. Compare the runs:

   ```bash
   python lib/compare_runs.py hidden-r1 hidden-r2 hidden-r3 hidden-r4 --openapi ~/Desktop/freya-final/hidden.openapi.json
   ```

2. Drop a run that has no export, an error line in the trace, or more static check errors than the best run.
3. Of the runs that are left, take the run with fewer open review items (`open` in the review line).
4. Talk to each run that is left once, with the brief's call variables:
   `python lib/chat.py <workflow_id> --vars '<call variables>' "Hello?"`. Drop a run whose first line breaks the
   brief's opening rule.
5. If runs are still equal, take the run with the shorter build time (equal scores are ranked by it).
6. Copy the chosen run to the submission names, without a change to the files:

   ```bash
   cp submission/hidden-r2.workflow.json submission/hidden.workflow.json
   cp submission/hidden-r2.trace.log submission/hidden.trace.log
   ```

   Write in `submission/CHOICE.md` which run you chose and why (one line for each run).

## After each run

1. Check that `submission/<slot>.workflow.json` exists and that `submission/<slot>.trace.log` has a `start` and an
   `end` line, and no key value (`grep -c fak_ submission/*.log` gives 0).
2. Run the static check: `python lib/check_workflow.py submission/<slot>.workflow.json --openapi <tool API file>`. It
   must give 0 errors.
3. Talk to the agent once: `python lib/chat.py <workflow_id> --vars '<call variables of the brief>' "Hello?"`. The first
   line must follow the brief's opening rule.
4. If the trace says "the export failed" or "the finish step failed" (Freya gave 503 or 504 at the end): wait until
   `python lib/platform_check.py <workflow_id>` says UP, then run `python3 build.py --export-only --slot <slot>`.
   This publishes the best tested version and exports it, and adds its lines to the same trace. Do not run the
   builder again for this.
5. If the run crashed in another way or the export is missing: find the cause in the trace, fix only the crash in
   the builder (commit it with a message that says it is a crash fix), and run the builder again on that brief.

## When the platform is down or slow

Seen on Saturday 2026-10-10 from 16:50 to 17:10 Istanbul time: chat gave 503, and for some minutes after, a tool call
took 6 to 11 seconds and simulations hung.

1. Check with `python lib/platform_check.py <workflow_id>`. Wait at least 2 minutes between two checks.
2. The builder does not change a workflow on an outage test, and it publishes the best tested version. A run without
   any test publishes its first checked draft.
3. A test that you stop on your side keeps running on Freya until it ends, and the next test waits for it. A
   simulation that runs more than 30 minutes is stuck: `python lib/sim_queue.py --cancel-stuck 30` cancels it. Do not stop a test unless the run is lost anyway. Before a new builder run, wait until
   `python lib/sim_queue.py` says "no simulation runs".
4. When the platform is up again and time is left, run the builder once more on the brief. Submit the run with the
   better test result, with the trace of that run.

## Submit (before 20:00 UTC)

1. Check that `submission/` holds only the hidden-brief files: the chosen `hidden.*`, the files of each run
   (`hidden-r1.*`, ...) and `CHOICE.md`. Commit `submission/` and push to GitHub.
2. Send the form to the address in the kit e-mail:

   ```json
   {
     "team": "<team name>",
     "repo": "https://github.com/<owner>/anvil-freya-builder",
     "commit": "<the commit of the builder that made the runs>",
     "run_command": "python3 build.py {brief_path} {tool_api_path}",
     "workflow": "submission/hidden.workflow.json",
     "trace": "submission/hidden.trace.log"
   }
   ```

3. The top ten teams get their repository cloned and the builder run again. Freya needs read access to the repository.

## Time plan

| UTC | Istanbul | What |
|---|---|---|
| 17:00 | 20:00 | Download, read the brief and the tool API file |
| 17:05 | 20:05 | hidden-r1 (up to 30 minutes) |
| 17:35 | 20:35 | hidden-r2. Checks of hidden-r1 during the run |
| 18:05 | 21:05 | hidden-r3. Checks of hidden-r2 during the run |
| 18:35 | 21:35 | hidden-r4. Checks of hidden-r3 during the run |
| 19:05 | 22:05 | Checks of hidden-r4. Choose the run (see "Choose the run to submit") |
| 19:20 | 22:20 | Commit, push, send the form |
| 20:00 | 23:00 | Close |

If a run crashes or Freya is down for long, skip the later runs: one finished run comes first. Do not start a run
after 19:25 UTC (22:25 Istanbul).
