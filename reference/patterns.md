# Patterns for Freya phone agents

What worked and what failed on the platform. Each item is general: it holds for any brief of this kind of call.
The kit documents (`$KIT/docs/*.md`) are the source of the platform facts. This file adds the design.

## The shape of a call

A collections-style call has stages. Give each stage its own node, so that each prompt is short and each exit is a
route that code can check:

1. `setup` (code, the initial node, passthrough): compute every date fact from the call variable `now` (never the
   real clock): today, the weekday, business days ahead, week ends, callback windows. Write them as text variables
   that the prompts show (`{{today_facts}}`), and as plain values that later code reads.
2. `opening` (conversation): the first sentence as a fixed line (`on_enter` type `tts`, with `{{title}} {{last_name}}`
   style variables). Find out who is on the line. Extract an enum (for example `who`: customer, someone_else,
   wrong_number, deceased, refuses, unclear) and route on it with `equals`. Never route on a free intent when an enum
   can carry it.
3. `someone_else` and other early exits (conversation): what the brief allows to tell a third party, and a callback
   if the brief has one. Nothing about the account.
4. `identity` (conversation): ask the security questions one at a time, call the verify tool after each answer. The
   result hook says what the answer means (passed, wrong with N left, hint such as a swapped day and month, all
   passed). Route on the tool's result variables: all passed, check ended, refused.
5. `load_account` (api_request, passthrough): the account tool in `pre_actions`, `response_mapping` on the node.
6. `account_facts` (code, passthrough): per product, everything the brief computes: the name in words, the amount
   as speech, the band, the deadline, the floor, the number of attempts, the allowed promise dates. Write one text
   block for the prompt (`{{account_facts}}`) and plain values for code. Put the product ids in the text: the model
   must copy them, never invent them.
7. `negotiate` (conversation): the debt statement, the ask, the attempts, the read-back, the write tools. The prompt
   carries the brief's rules for this stage in order, and the facts block.
8. `close`: one `close_call`-style tool call that is the last tool call, then an `end_call` node. Route to the
   `end_call` node on the close tool's success counter or result.

Merge or split stages when the brief needs it. A stage with strict rules of its own gets its own node.

## Dates and numbers: code, not the model

- The model gets dates wrong: weekends, holidays, "the n-th business day", "next Friday" said on a Friday. Compute
  them in code from `now` and give the model a lookup table: for each day of the coming weeks, the date, the weekday,
  and whether it is allowed as a promise date (and why not: weekend, holiday, after the deadline, before today), and
  which day to offer in its place.
- Give each relative phrase that the brief defines its date in the table ("this Friday", "next Friday", "end of the
  week", the last business day of this week and of next week). Use the brief's own definition of each phrase.
- Amounts: write them as speech in code (`money(420)` gives "420 dollars"). The model said "dollars365" when it got
  a bare number.
- Counters (attempts, wrong answers): keep them in the tool results or in code, not in the model's memory.

## Tools

- Make tools with `lib/tools_from_openapi.py`. Every body field keeps the API's type, description and enum.
- A tool description says when to call it: "CALL it ... ". A plain description lets the model say the action in words
  and never call the tool.
- After every tool result the model must speak or call the next tool. The result hook's `what_to_do_next` gives it
  the next move. Write the guide texts from the brief: what a failure means (retry once? say it failed?), what each
  result field means.
- Write tools get `maxRetries` 0. Retries that the brief asks for (for example "try once more") are the model's job,
  driven by the hook text, so that each try is visible in the ledger.
- A tool is available only in nodes that list it. List the close tool in every conversation node that can end the
  call.
- Never let the model invent an id. Ids come from tool results: show them in the facts block.

## Hooks: code around each tool call

- A `pre_process_code` hook can fix what the model filled in before the request goes out: `config["body"]` is the
  request body. Use it to normalize values: a date said in words to `YYYY-MM-DD` (read a date of numbers only in the
  order that the brief gives), spoken digits to digits, a time to `HH:MM`, an amount to a number.
- A close guard: a `pre_process_code` hook on the close tool sets the outcome and the reason from what the tools did
  (`vars` holds `<tool>_response.data.*` of earlier calls). For example, a recorded promise means the promise outcome
  unless a later transfer replaces it, and an ended identity check means its own outcome. The model picks the
  outcome in words, the guard makes the ledger right. Write the guard from the brief's outcome table.
- A `post_process_code` hook can count in `vars` (for example the failures of a write tool) and give a different
  `what_to_do_next` the second time: "try once more" versus "say that it failed and close". Do not leave a retry
  count to the model.
- Say what to do in the same message: "thank the customer, say goodbye, and in the same message call the close tool".
  A model that waits for the next user turn after a result can lose the turn.

## Routes

- Route on tool results and extracted enums with `equals`, `greater_than`, `is_set`. Test booleans as both "true"
  and "True".
- A result variable is `<tool>_response.data.<field>`. A mapped variable (`response_mapping` path `data.<field>`) is
  safer to read in prompts.
- Put specific transitions first and a self-transition (`always` to the same node) last in conversation nodes, so
  the call never stalls.
- Every passthrough node ends with an `always` transition.

## Prompts

- `system_prompt`: identity, language, tone, the honesty rule, the one-question-at-a-time rule, and the rules that
  hold in every stage (words never said before verification, the robot question, the scam question).
- `task_message`: this stage's rules in the brief's order, then the facts block. Say which tool to call when.
- Copy fixed sentences of the brief word for word into the prompt and tell the model to say them exactly ("say this
  sentence: ..."). The judge checks them.
- Never name nodes or describe routing in a prompt.
- Counted offers (persuasion attempts, a floor that may be offered once): a question of the customer gets an answer
  with the fact only. Do not end the answer with the offer again ("Would you be able to pay that today?"). The judge
  counts an offer said again as a new offer. Write in the prompt: "When the customer asks a question, answer it and
  wait. Do not repeat an offer."
- After a step that passes (a verified answer), say what comes next in the same message. A bare "Thank you." makes
  the customer ask what the call is about.

## Honesty and closing

- The model must never say "recorded", "scheduled", "transferred" before the tool result says ok.
- The close tool is the last tool call. Say the goodbye before it. After a successful close, route to an `end_call`
  node with `message_mode` "none".
- Every path of the call ends with exactly one close call with the brief's outcome and reason. Give the model the
  outcome table with the reason values, and the rule for each row.

## Testing

- `lib/chat.py` talks to the published workflow in seconds. `run_cases.py` is the real test (3 to 11 minutes).
- Read failed calls with `lib/analyze_call.py`: the ROUTE lines show why a transition did or did not fire.
- One green run is a hint, not a proof. Fix the cause of a failure in the design, so that other customers pass too.
