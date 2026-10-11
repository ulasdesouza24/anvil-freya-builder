# Choice of the run to submit

Builder commit of runs r3 and r4: 94af20a (r1 ran at a8f8982, r2 at c8cdf52/a8f8982). All four runs: export, 0 error
lines in the trace, 0 static check errors. Each run was replayed in chat on the six example scenarios of the case,
against our mock (https://freya-statement-mock.umet9711.workers.dev).

- hidden-r1 (21 min): 5 of 6 examples right, 1 in part (asked again for a week the customer had named).
- hidden-r2 (17 min): 6 of 6, but one big node and an exit tool that calls a read service; built before the
  20:55 document came in.
- hidden-r3 (19 min): 6 of 6, one end node per exit, lists the other weeks, asks again on a vague yes; read all 19
  documents. CHOSEN.
- hidden-r4 (15 min): 5 of 6 (refuses to name even the last four digits), one big node, 1 open review item.

Submitted: submission/final.workflow.json = hidden-r3.workflow.json, submission/final.session.jsonl = the builder's
session log of run r3 (submission/final.trace.log = its text trace). The files were copied, not changed.
