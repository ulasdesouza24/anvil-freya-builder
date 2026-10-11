# Review checklist

Use this list after the first save, and again after each large change. Each item comes from a failure that a test
showed. A draft that was not tested on practice customers fails some of these items in most runs.

For each item, find the place in `make.py` that carries it: a code line, a hook, a route, or a prompt sentence. Write
the result in `work/<slot>/review.md`, one line for each item: `OK <where>`, `FIXED <what>`, or `N/A <why>`. Fix every
item that has no place. Then check, save, and talk to the agent again.

## A. Tools and the close

1. **The close tool is the last call, and it is alone.** The close tool's description and the stage prompt say:
   "Call this tool alone, after the results of all other tools." The post-hook of every other write tool (transfer,
   callback, promise, note) says in `what_to_do_next` what to do next, with the close values when the call ends
   there ("Now say goodbye and call the close tool with outcome X and reason Y"). Seen: the close came before the
   transfer, and the transfer did not run.
2. **The close guard covers every row of the outcome table.** It reads `<tool>_requested`,
   `<tool>_request__<field>` and `<tool>_result__<field>`, not only the results. List each outcome row and the
   condition that sets it.
3. **Several items, one write each.** The write tool's post-hook names the written items and the open items.
4. **No claim before success.** "Recorded", "scheduled" and "transferred" come only from a result that says ok.
   A word that the brief forbids before an event does not appear earlier in another sense (the opening sentence).
5. **Retries are counted in a post-hook**, not by the model.

## B. Which rule comes first

6. **Rules that come before the ask.** When the brief says that a rule comes before the payment ask or before
   persuasion (hardship, dispute, already paid, a third party, a request for a human), the stage prompt puts these
   rules FIRST, before the ask, and says: "If the customer already said one of these, do not ask for a payment."
   The extraction fields catch them in any part of a message. Seen: the customer said "I lost my job and cannot
   pay", and the agent asked "Can you make this payment today?".
7. **Nothing about the account before verification**: no product, no amount, no reason for the call. Also not to
   a third party, and not when the customer asks.
8. **Every security answer goes to the verify tool**, also when the message holds a question. Never a partial
   value. Parts are joined in the spoken order.

## C. Counted offers

9. **Each counted offer has a count in code or a written plan in the facts block** (an offer that the brief allows
   once, persuasion attempts per item). The prompt says: "Each offer is made once. When the customer asks a
   question, answer it and wait. Do not repeat an offer." Seen: the floor offered three times.
10. **An objection changes only the value that the customer objects to** (date or amount).
11. **The agent proposes the values** when the brief says so, one value at a time, as a yes-or-no question.

## D. Dates and numbers

12. **Today comes first in the facts block**, from the call variable. Date code calls
    `spoken_date(text, order, year, today)`. Amounts are said with `money()` (never "dollars142.50").
13. **A loop that asks for a value asks at most twice**, then proposes a value as a yes-or-no question. The count is
    in `vars`. A route into a check step on "<value> is set" has logic "and" with "<value> not_equals ''", and the
    check step clears the value. Without this the route fires on every turn and the write tool is never called.
14. **A vague period** ("next week", "when my salary comes") follows the brief's rule for it exactly.

## E. How customers talk

15. **A long message is read in full.** Extraction field descriptions say: "the customer may say this inside a
    longer story".
16. **Small talk, a question back, a stall or a cut-off reply is not a refusal.** A refusal is a no to the question
    itself.

## F. Every path

17. **Each outcome row has a path**: write a table in `review.md` with the outcome, the route or tool that leads to
    it, and the close values. Check each path with `lib/chat.py` or by running its code locally.
18. **Fixed sentences of the brief are copied word for word** into the prompt with "say exactly".
