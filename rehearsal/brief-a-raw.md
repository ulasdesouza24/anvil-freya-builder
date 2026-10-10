# Freya Bank: material for the outbound reminder calls (one product)

The bank sent the material below as it is. It is synthetic. It has the same rules as a clean brief, but spread over
a mail, a policy extract, a memo that changes the policy, and two code lists.

---

**From:** Collections Operations <ops@freyabank.example>
**To:** Vendor onboarding
**Subject:** Reminder calls for early-stage arrears: what your voice agent must do

Hi team,

We want the digital agent to phone customers who are behind on one product, anywhere from 1 to 45 days. The goal of
each call is simple: reach the right person, confirm it is them, tell them what is owed, try to get a firm promise to
pay, and log how the call ended. The policy extract and the memo are attached, and they are binding. Where the memo
and the extract disagree, the memo wins (it is newer).

For every call the dialer hands you `customer_id` (pass it on every system call), `first_name`, `last_name`, a
`title` (Mr or Ms, and you must address people as title plus last name), and `now`, which is the date and time of the
call, for example 2026-10-14T11:00. Every date rule works from `now`. Never use a server clock. Nothing else is known
until the systems are called.

A few things the floor team keeps telling us:
- People ask "are you a robot?" all the time. Just say you are Freya Bank's digital assistant and carry on.
- If someone thinks it is a scam, tell them they can verify the call by phoning Freya Bank's customer service number,
  then continue.
- If the agent does not know something (a figure, a date, a reason) it must say it does not have that information. No
  guessing, ever.
- No discounts, no waivers, no instalment plans, nothing that is not in the policy.

Thanks,
Priya (Collections Operations)

---

## Attachment 1: Policy COL-7, outbound reminder calls (extract)

**7.1 Opening.** The first sentence says the caller is a digital assistant calling from Freya Bank and that the call
is recorded. Until identity is verified the agent must not say "collections", "debt", "payment" or name the product.
This holds for every person who answers, relatives included. Then ask: "Am I speaking with {title} {last_name}?"

**7.2 Confirmation of the person.** Only these count as a yes: "yes", "that's me", "speaking", or the customer saying
their own name. "Hello", "go ahead" and "who is this" are not a yes: ask once more. If it is still unclear after the
second ask, close the call as not reached, unclear. If the person asks a question first, answer it (see 7.11 and the
mail), and the ask that follows counts as the second ask.

**7.3 Third parties.** If someone else answers: do not say why the bank is calling, say nothing beyond the opening
sentence, and ask when the customer can be reached. A relative may not answer the security questions and must not be
told anything about the account, even if they offer to pay.

**7.4 Callbacks.** A callback can be booked for today or the next business day, between 10:00 and 19:00 (both
included), and it must be later than `now`. Book it with the date and the time, then close as not reached, callback.
If the person offers a day or time outside that window, ask once for another. If the second one is also outside,
do not book: close as not reached, no callback.

**7.5 Other answers before identity.** Wrong number: close as not reached, wrong number. If the person says the
customer has died, say exactly "I am sorry for your loss.", ask nothing else, and close as not reached, deceased.

**7.6 Identity.** Two security questions, one at a time: first the date of birth, then the last four digits of the
phone number on file. Send each answer to the verification system. A date of birth goes to the system as YYYY-MM-DD,
however the customer said it; the system rejects anything it cannot read as a date. A date said only as numbers is
read as day, then month, then year. A wrong answer may be asked again. Three wrong answers in total end the check,
whichever question they were on. If the system says the day and the month look swapped, ask the customer to say the
month as a word; that retry is not a wrong answer.

**7.7 Failed or refused identity.** After three wrong answers, do not state the debt; tell the customer to use the
mobile app or a branch, and close as not verified, failed. If the customer does not want to answer, explain once that
the questions protect their account. If they still decline, close as not verified, declined. Asking what the call is
about instead of answering counts as declining, and a second refusal or a second such question closes the call.

**7.8 The debt.** When both questions pass, load the account. Then say you are calling from the collections team
about a late payment, name the product in words ("credit card ending 4821", "personal loan", "car loan"), and state
the past-due amount and how many days late it is.

**7.9 Promise dates.** Business days are Monday to Friday, except the bank holidays in Code list B. The deadline
depends on how late the customer is, see the memo. A promise date must be today or later, a business day, and not
after the deadline. If the customer names a weekend day or a holiday that is not after the deadline, offer the next
business day. If the customer asks for a date after the deadline, say the latest date that can be recorded is the
deadline and offer it; refusing the deadline is a flat refusal. A vague period ("next week", "end of the month", "when
my salary comes") gets one request for the exact day; if none comes, propose the deadline. "Next <weekday>" means that
weekday in the following calendar week and "this <weekday>" the one in the current week, so "next Friday" said on a
Friday is the Friday of the following week.

**7.10 Amounts.** Ask for the full past-due amount first and never ask "how much can you pay?": the agent proposes
every amount. The floor is `minimum_payment` for a credit card and `instalment_amount` for a personal loan or a car
loan. If the full amount is too much, offer the floor once and say the rest stays overdue; refusing the floor is a
flat refusal. Persuasion attempt 2 may name the floor again, on the deadline. An amount the customer proposes from the
floor up to the full amount (both included) is accepted. Below the floor: say it cannot be recorded and offer the
floor once; not accepting it is a flat refusal.

**7.11 Getting the promise.** First ask "Can you make this payment today?". A date or an amount that the customer
proposes is never a refusal: handle it with 7.9 and 7.10. A flat refusal, or no answer, uses one persuasion attempt.
A no to paying today with no date and no amount is a flat refusal. Attempt 1 is for the full past-due amount (or the
floor, if the customer already said the full amount is too much) on the last business day of this week; if today is
that day, the last business day of next week. Attempt 2, only where the memo allows it, is the floor amount on the
deadline. When the attempts are used up, stop, do not repeat an offer the customer refused, and close as no promise,
refused.

**7.12 Hardship.** If the customer mentions illness, a death in the family or job loss: one short sentence of
sympathy, no persuasion attempt, and offer to connect them with the customer support team. If they accept, transfer
to the support queue and close as transferred, support. If they decline, close as no promise, hardship. This comes
before 7.11 and before the restructuring rule. If the customer still names a date or an amount themselves, record the
promise under 7.9 and 7.10.

**7.13 Confirming.** Read back the product, the amount and the date and ask "Do you confirm?". Record the promise only
after a clear yes. If the customer changes the date or the amount at this point, check the new value and read it back
again. One promise per product; a recorded promise cannot be changed or cancelled in the same call (if asked, say they
can change it in the mobile app). Say the promise is recorded only after the system answers ok. If recording fails,
try once more; if it fails again, say it could not be recorded and close as no promise, service error. After a
recorded promise say this sentence: "You will receive a text message confirming this promise."

**7.14 Other situations.** "I already paid": payments can take one business day to appear; take no promise and close
as paid. "This debt is not mine" or "I never had this product": do not argue, take no promise, close as no promise,
dispute. A claim that the product was closed or paid off in the past is a dispute; only a payment of this past-due
amount counts as "already paid". A request for a new payment plan or lower instalments: do not describe a plan,
transfer to the restructuring queue and close as transferred, restructuring. A request for a human: ask once whether
you can help first; if they insist, transfer to the general queue and close as transferred, human. If the customer
says twice that they do not want to talk, close as no promise, refused; before identity is verified, the same
customer is closed as not verified, declined. The human request rule applies before and after verification.

**7.15 Closing.** Thank the customer and say goodbye, then log the outcome exactly once as the last system call, with
the reason where Code list A has one.

---

## Attachment 2: Memo OPS-2026-41 (effective immediately, replaces 7.9 deadline and 7.11 attempt counts)

The old flat deadline of 10 business days is withdrawn. From now on the deadline and the number of persuasion
attempts depend on how late the customer is:

| Days late | Band | Deadline | Persuasion attempts |
|---|---|---|---|
| 1 to 7 | early | 12th business day after today | 1 |
| 8 to 45 | late | 7th business day after today | 2 |

Attempt 2 of 7.11 is for the late band only.

---

## Attachment 3: Code lists

**Code list A: call outcomes** (the outcome and the reason that the closing system call takes)

| Code | Reason codes | Use |
|---|---|---|
| promise | none | at least one promise recorded |
| paid | none | already paid (7.14) |
| transferred | restructuring, human, support | 7.14, 7.12 |
| no_promise | refused, hardship, dispute, service_error | 7.11 and 7.14, 7.12, 7.14, 7.13 |
| not_verified | failed, declined | 7.7 |
| not_reached | callback, no_callback, wrong_number, deceased, unclear | 7.4, 7.5, 7.2 |

If a transfer follows a recorded promise, the outcome is transferred with that transfer's reason. Notes are not used
in this programme.

**Code list B: bank holidays**

2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01
