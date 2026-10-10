---
name: build-freya-agent
description: Build a Freya phone agent (a workflow) from a bank's brief and its tool API, check it, test it when practice customers exist, and fix what fails. Use for every build request of this builder.
---

# Build a Freya phone agent from a brief

You are a builder. A program will score the phone agent that you create on customers that you never see, three
times each, on several calendar days. A customer counts only when all three calls pass. So build an agent that is
right every time: put rules in code and routes, not only in prompts.

Work only inside the builder folder: the brief files and the tool API file in `work/<slot>/input/`, the kit copy in
`kit/`, the helpers in `lib/`, the patterns in `reference/`. Never read files outside it, and never read the output
of another builder. Use only what the given brief files and the given tool API file say. A later brief file builds on the earlier ones.
Never use a rule, value or name that the brief does not give. The brief can be a clean specification, or raw bank
material (a mail, a policy extract, a memo that changes it, a code list). With raw material, the newest memo wins
over the policy text that it changes.

Read `reference/patterns.md` (in this folder's parent: `../../../reference/patterns.md`, path from the builder root:
`reference/patterns.md`) before you design. It holds what worked and what failed on the platform.

## Time

The prompt gives a Unix deadline. Run `date +%s` before each long step. Keep 4 minutes at the end for the final save
and the export. When the time is short, stop testing and save the best workflow that you have.

## Steps

1. **Read.** The brief files, the tool API file, then `kit/docs/workflow-format.md` and `kit/docs/tools-and-code.md`
   (read both fully the first time). Skim `kit/examples/base-agent.json` for the JSON shape only.

2. **Rule ledger.** Write `work/<slot>/rules.md`: every rule of the brief as one numbered line, in the brief's words,
   plus every table (bands, deadlines, outcomes, codes, holidays) copied exactly. Include the call variables and what
   each tool returns. Mark rules that change an earlier brief or an earlier policy text. Do not skip a rule because
   it looks rare: most failed customers come from one skipped rule.

3. **Design.** Write `work/<slot>/design.md`: the nodes, what each node does, its tools, its exits (routes) and which
   ledger rules it carries. Follow the patterns in `reference/patterns.md`. Every number and every date rule
   (business days, deadlines, windows, floors, attempt counts, "next Friday") is computed by code, never by the model.

4. **Write the generator.** Write `work/<slot>/make.py`, a Python script that builds the workflow JSON and writes
   `work/<slot>/workflow.json`. Use the helpers, do not copy their text:
   - `lib/tools_from_openapi.py`: `tools(openapi, guide)` gives one api_call tool per path, with the body fields and
     enums of the API, the customer id baked, and a result hook that adds `what_to_do_next`. Write the `guide` from
     the brief: for each tool, the text for a failure, and texts for result fields (for example a hint value).
   - `lib/pycode.py`: `node(name, body, next_node)` gives a code node. `run(body, sample_vars)` runs the body locally.
     The body may use the helpers in `pycode.HELPERS` (parse_now, add_business_days, is_business_day,
     next_business_day, last_business_day_of_week, weekday_in_week, spoken, money, get_list, num, ...).
   Run every code body locally with sample variables (call variables of the brief, and tool results shaped like the
   tool API) before you put it in the workflow. Print the values and check them against the brief by hand.

5. **Check.** `python lib/check_workflow.py work/<slot>/workflow.json --openapi <tool API file>` must give 0 errors.
   Then a dry run: `python -c "import sys,json; sys.path.insert(0,'kit'); import freya; print(freya.validate_workflow('<slot>', json.load(open('work/<slot>/workflow.json'))))"`.

6. **Save and publish.** From the builder root (this keeps the slot's ids in `.freya-agents.json`):
   `python -c "import sys,json; sys.path.insert(0,'kit'); import freya; print(json.dumps(freya.save_workflow('<slot>', json.load(open('work/<slot>/workflow.json')))))"`.

7. **Talk to it.** `python lib/chat.py <workflow_id> --case <a practice case id> "<user turn>" ...` when practice
   customers exist, else `--vars '<call variables>'`. Check the first line, the identity step and one route.

8. **Test, when the prompt says that practice customers exist.** Save first, then:
   `python lib/test.py <slot> <the options from the prompt> --out work/<slot>/run<N>.json` (a new N for each test).
   A run takes 3 to 11 minutes. You may start it in the background (`nohup ... > work/<slot>/run<N>.log 2>&1 &`) and
   use `lib/chat.py` meanwhile. A test runs the version that was published when it started, and `lib/test.py`
   records the result for that version. At the end the builder publishes the best tested version, not the last one,
   so a late change that makes the agent worse does no harm. Do not start a large change in the last 8 minutes: it
   cannot be tested.
   **Never stop a test** (no `kill`, `pkill`, `timeout` or Ctrl-C), also when you find a bug during it. Freya cannot stop a
   simulation: it runs on to the end, and your next test waits for it, so a stopped test costs its full time and
   gives no result. Fix the bug, save, and start the next test when the running one ends. Start only one test at a
   time. `python lib/sim_queue.py` shows what runs.
   A platform outage looks like this: every customer fails with no tool call, the median agent turn is 0 s, or chat
   gives 503, or every tool call fails. Then do not change the workflow. Run
   `python lib/platform_check.py <workflow_id> <tool API file>` every 2 minutes (not
   more often) until it says UP, then test again. If the platform stays down, save the best version and stop.
   Read every FAIL line, then `python lib/analyze_call.py --run work/<slot>/run1.json` for the events of the failed
   calls. Find the cause in the workflow (a route that did not fire, a missing rule, a wrong number), fix it in
   `make.py`, check, save, test again. Fix causes, not one customer: the scored customers are different people.
   When every customer passes and at least 8 minutes are left, run once more with `--style in_words` or
   `--style pieces` (amounts and dates in words, numbers in two parts): the scored customers talk like that. A
   customer that passes only sometimes is a failure: the score needs three passes out of three.

9. **Coverage.** Write `work/<slot>/coverage.md`: for each ledger rule, the node, route, tool or code that carries
   it. Fix every rule without a place. Then save again.

10. **Finish** with one line: workflow_id, agent_id, and the result of the last test (or "no practice customers").

## Rules

- Never edit the agent on the platform by hand. Change `make.py`, run it, save.
- The agent must never say that a thing is recorded, scheduled or transferred when the tool call failed or was not made.
- Leave `agent_config` out of the workflow.
- One slot, updated in place. Never create a new workflow for each try.
