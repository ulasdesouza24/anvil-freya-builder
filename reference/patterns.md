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
4. `identity` (conversation): ask the security questions one at a time, call the verify tool after EACH answer,
   also when the same message holds a question or a complaint ("1990. How much do I owe?"): check the answer first,
   then reply. Seen in a test: the model answered the question, skipped the check of a wrong answer, and so gave the
   customer one more try than the brief allows. Never judge an answer yourself: only the tool result counts. The
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

## How customers talk

The scored customers talk like people: they give a number in two parts, correct themselves, say amounts and dates in
words, ask back, and talk about other things. Write these rules into the prompts of every node that collects a value:

- Never call a check tool (identity, verification) with a partial value. A wrong-looking answer costs the customer
  one of the allowed tries. Call it only when the value is complete in the form that the tool API describes (for
  example all four digits, a full date with the year). Write this into the tool description and the node prompt.
- A partial value: keep the part that the customer gave and ask only for the missing part ("And the year?"). Do not
  ask for the whole value again: a customer who talks in pieces repeats the same piece.
- Join the parts of a value in the order that the customer said them: the first part first. "Forty four" then "one
  zero" is 4410, never 1044. Seen in a test: the model put the later part first three times and used up every try
  of the security check. Write this into the description of every field that can come in parts.
- Ask for one value at a time, and propose the full offer (amount and date) as one yes-or-no question. "Can you pay
  300 dollars? If so, on what date?" asks two things: the reply "30" (the 30th) was taken as 30 dollars, the agent
  dropped to the floor, and the promise was 90 dollars instead of 300. A bare number that could be a day or an
  amount is not clear: ask what it means. Never lower an amount because of an unclear reply.
- A number said over two turns ("five..." then "forty") is one number (540). A reply that ends in "..." or stops in
  the middle is not finished: wait for the rest or ask for it. Never act on a part of a number.
- A self-correction ("the 21st, sorry, the 20th") means the corrected value.
- A cut-off or unclear reply is not a refusal and not a confirmation. A refusal counts only when the customer says it
  clearly. Ask once more.
- A long, chatty message can hold the one fact that decides the stage in its middle: a date, an amount, a hardship,
  a third party, a refusal. Read the whole message. Write the extraction field descriptions so: "the customer may say
  this inside a longer story; take it from any part of the message". Seen in one test run of talkative customers
  (7/10): a date of the customer's own inside a story was taken as a refusal, a hardship inside small talk was missed
  and persuasion went on, and stalling after two wrong security answers was closed as "declined".
- Small talk, a story, a question back or a stall is not a refusal and not an answer. Answer it in one sentence, then
  ask the same question again. A refusal counts only when the customer says no to the question itself.
- When the brief says that the agent proposes the values (an amount, a date), the agent never asks the customer for
  them. When the customer accepts a date without an amount, the amount is the one of the current offer.
- An objection changes only the value that the customer objects to. A date that is too late gets a new date (for
  example the deadline) with the SAME amount. An amount that is too high gets the lower amount (for example the
  floor) with the same date. Seen in a test: "I can only pay on the 6th" (after the deadline) got "the deadline with
  the floor", and the bank lost 850 dollars of the promise. Put this rule in the prompt of the stage, and give the
  offer plan in the facts block as separate amount and date steps.

## Dates and numbers: code, not the model

- The model gets dates wrong: weekends, holidays, "the n-th business day", "next Friday" said on a Friday. Compute
  them in code from `now` and give the model a lookup table: for each day of the coming weeks, the date, the weekday,
  and whether it is allowed as a promise date (and why not: weekend, holiday, after the deadline, before today), and
  which day to offer in its place.
- A lookup table is not enough: in tests the model read the wrong row and offered a later day than the next
  business day. Check a date that the customer names with code, every time:
  1. In the negotiation node, extract it: `{"name": "named_date", "type": "date", "min_confidence": 0.6}`.
  2. A transition (before the self-transition) goes to a code node when `named_date` is set and differs from
     `checked_date`. The code node reads `named_date` and the item's rules (computed earlier), and writes
     `checked_date` (the same value) and `date_verdict`: one sentence such as "2026-10-26 is a bank holiday: offer
     Tuesday 27 October 2026 instead" or "2026-10-23 is allowed: read it back". Its last transition goes back to the
     negotiation node (`always`).
  3. The negotiation prompt shows `{{date_verdict}}` and says: "The DATE CHECK line is the only source of truth for a
     date that the customer named. Offer exactly the date that it gives." On re-entry the node must not repeat its
     opening line (`on_enter_first_entry_only`, or an `on_enter` prompt that continues the conversation).
  Test the code body locally with each kind of date: a weekend, a holiday, after the deadline, before today, allowed.
- Give each relative phrase that the brief defines its date in the table ("this Friday", "next Friday", "end of the
  week", the last business day of this week and of next week). Use the brief's own definition of each phrase.
- Amounts: write them as speech in code (`money(420)` gives "420 dollars"). The model said "dollars365" when it got
  a bare number.
- Counters (attempts, wrong answers): keep them in the tool results or in code, not in the model's memory.
- Offer plans: when the brief counts persuasion attempts (per product, per band), compute the full plan in code and
  put it in the facts block for each item: "attempt 1: <amount> on <date>; attempt 2: <amount> on <date>; then
  refused". In the prompt, add the check: "Before you record a refusal for an item, make sure that you said every
  attempt of its plan." With several items, the model loses count if it has no written plan.

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

- `lib/tools_from_openapi.py` gives each tool a pre-hook that turns spoken values into the API's form, from the
  field's type, format and description: a date field gets `YYYY-MM-DD` from "the twenty-second of October", a number
  field gets 455 from "four hundred and fifty-five", a field described with digits gets "9904" from "nine nine oh
  four", a field for a date or digits (a security answer) gets the one that fits. It changes a value only when the
  result is clear. Set the order of a date said only in numbers with the guide key `_date_order` ("DMY" or "MDY")
  from the brief. Change the plan of a field with `guide[tool]["normalize"] = {field: "date"|"number"|"digits"|"none"}`.
- Code steps have the same helpers (`words_to_number`, `digits`, `spoken_date`) for values that come from speech.

- A `pre_process_code` hook can fix what the model filled in before the request goes out: `config["body"]` is the
  request body. Use it to normalize values: a date said in words to `YYYY-MM-DD` (read a date of numbers only in the
  order that the brief gives), spoken digits to digits, a time to `HH:MM`, an amount to a number.
- A close guard: a `pre_process_code` hook on the close tool sets the outcome and the reason from what the tools did
  (`vars` holds `<tool>_response.data.*` of earlier calls). For example, a recorded promise means the promise outcome
  unless a later transfer replaces it, and an ended identity check means its own outcome. The model picks the
  outcome in words, the guard makes the ledger right. Write the guard from the brief's outcome table.
  The model can call a write tool and the close tool in the same turn. Then the guard runs before the write's
  result exists. Seen in a test, 3 runs of 3: a transfer and a close together, closed as a refusal. So the guard
  reads the requests too: the pre-hook of every write tool sets `<tool>_requested` and `<tool>_request__<field>`
  (for example `transfer_to_agent_request__queue`) at the time of the call. A transfer that was requested and did
  not fail counts as a transfer. Also write in the close tool's description and in the prompt: "Call this tool
  alone, after the results of all other tools."
- A `post_process_code` hook can count in `vars` (for example the failures of a write tool) and give a different
  `what_to_do_next` the second time: "try once more" versus "say that it failed and close". Do not leave a retry
  count to the model.
- Several items, one write each (a promise per product): the post-hook of the write tool keeps the written item ids
  in `vars` and names the open ones in `what_to_do_next`: "Written: p1, p3. Still open: p2 (personal loan). Call the
  write tool for p2 now, before anything else." The account tool's result vars give the full list. The close guard
  reads the same list. Seen in a test: the model wrote two of three confirmed promises, closed the call, and called
  the write tool after the close.
- Say what to do in the same message: "thank the customer, say goodbye, and in the same message call the close tool".
  A model that waits for the next user turn after a result can lose the turn.

## Tool results in code steps

- A code step does not see the result keys that the engine writes (`<tool>_response.data.*`), and a
  `response_mapping` of a list sets nothing. Both were seen on the platform: a facts step found no products.
- The result hook of each generated tool writes every result field into a variable that code steps and prompts can
  read: `<tool>_result__<field>` (for example `get_account_result__products`). A list or an object is JSON text: read
  it with `get_list(vars, "get_account_result__products")` or `as_list(...)`. A list also gets
  `<tool>_result__<field>_count`.
- A tool in the `pre_actions` of an `api_request` node runs the same hooks.
- Test the code step locally with these variables, shaped as JSON text, before you save.

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
- A word that the brief forbids before an event (for example "recorded" before a successful promise) must not
  appear earlier in another sense. The judge reads such a check word by word: "This call is recorded" in the opening
  failed "does not say 'recorded' before a successful call" in 2 of 3 runs. When the brief gives the meaning and not
  the exact words, use another form ("We record this call."). When the brief gives the exact sentence, keep it.
- Copy fixed sentences of the brief word for word into the prompt and tell the model to say them exactly ("say this
  sentence: ..."). The judge checks them.
- Never name nodes or describe routing in a prompt.
- Counted offers (persuasion attempts, a floor that may be offered once): a question of the customer gets an answer
  with the fact only. Do not end the answer with the offer again ("Would you be able to pay that today?"). The judge
  counts an offer said again as a new offer. Write in the prompt: "When the customer asks a question, answer it and
  wait. Do not repeat an offer."
- Begin the facts block with today, from the call variable: "TODAY is Friday 16 October 2026 (2026-10-16). 'Today'
  always means this date." Without this line the model takes today from its own clock and gets weekdays, deadlines
  and "tomorrow" wrong. A pre-hook of a tool with a date field checks the date against today too.
- After a step that passes (a verified answer), say what comes next in the same message. A bare "Thank you." makes
  the customer ask what the call is about.

## Honesty and closing

- The model must never say "recorded", "scheduled", "transferred" before the tool result says ok.
- The close tool is the last tool call. Say the goodbye before it. After a successful close, route to an `end_call`
  node with `message_mode` "none".
- Every path of the call ends with exactly one close call with the brief's outcome and reason. Give the model the
  outcome table with the reason values, and the rule for each row.

## Testing

- `lib/chat.py` talks to the published workflow in seconds. `lib/test.py` (it runs `run_cases.py`) is the real test
  (3 to 11 minutes). A test that you stop keeps running on Freya, and the next test waits for it: never stop one.
- Read failed calls with `lib/analyze_call.py`: the ROUTE lines show why a transition did or did not fire.
- One green run is a hint, not a proof. Fix the cause of a failure in the design, so that other customers pass too.
