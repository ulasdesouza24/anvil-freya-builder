---
name: build-freya-agent
description: Build a Freya phone agent (a workflow) from a bank's brief and its tool API, check it, test it when practice customers exist, and fix what fails. Use for every build request of this builder.
---

# Build a Freya phone agent from a brief

You are a builder. A program will score the phone agent that you create on customers that you never see, three
times each, on several calendar days. A customer counts only when all three calls pass. So build an agent that is
right every time: put rules in code and routes, not only in prompts.

Use only what the given brief files and the given tool API file say. A later brief file builds on the earlier ones.
Never use a rule, value or name that the brief does not give. The brief can be a clean specification, or raw bank
material (a mail, a policy extract, a memo that changes it, a code list). With raw material, the newest memo wins
over the policy text that it changes.

Read `reference/patterns.md` (in this folder's parent: `../../../reference/patterns.md`, path from the builder root:
`reference/patterns.md`) before you design. It holds what worked and what failed on the platform.

## Time

The prompt gives a Unix deadline. Run `date +%s` before each long step. Keep 4 minutes at the end for the final save
and the export. When the time is short, stop testing and save the best workflow that you have.

## Steps

1. **Read.** The brief files, the tool API file, then `$KIT/docs/workflow-format.md` and `$KIT/docs/tools-and-code.md`
   (read both fully the first time). Skim `$KIT/examples/base-agent.json` for the JSON shape only.

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
   Then a dry run: `python -c "import sys,json; sys.path.insert(0,'$KIT'); import freya; print(freya.validate_workflow('<slot>', json.load(open('work/<slot>/workflow.json'))))"`.

6. **Save and publish.** From the builder root (this keeps the slot's ids in `.freya-agents.json`):
   `python -c "import sys,json; sys.path.insert(0,'$KIT'); import freya; print(json.dumps(freya.save_workflow('<slot>', json.load(open('work/<slot>/workflow.json')))))"`.

7. **Talk to it.** `python lib/chat.py <workflow_id> --case <a practice case id> "<user turn>" ...` when practice
   customers exist, else `--vars '<call variables>'`. Check the first line, the identity step and one route.

8. **Test, when the prompt says that practice customers exist.** In the foreground:
   `python $KIT/tools/run_cases.py <agent_id> --brief <A|B> --out work/<slot>/run1.json`. A run takes 3 to 11 minutes.
   Read every FAIL line, then `python lib/analyze_call.py --run work/<slot>/run1.json` for the events of the failed
   calls. Find the cause in the workflow (a route that did not fire, a missing rule, a wrong number), fix it in
   `make.py`, check, save, test again. Fix causes, not one customer: the scored customers are different people.

9. **Coverage.** Write `work/<slot>/coverage.md`: for each ledger rule, the node, route, tool or code that carries
   it. Fix every rule without a place. Then save again.

10. **Finish** with one line: workflow_id, agent_id, and the result of the last test (or "no practice customers").

## Rules

- Never edit the agent on the platform by hand. Change `make.py`, run it, save.
- The agent must never say that a thing is recorded, scheduled or transferred when the tool call failed or was not made.
- Leave `agent_config` out of the workflow.
- One slot, updated in place. Never create a new workflow for each try.
