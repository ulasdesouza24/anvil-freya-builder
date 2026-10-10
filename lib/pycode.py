"""Python for Freya code steps: tested helper functions, a node builder, and a local runner.

A Freya code step runs one snippet with a dict `vars` (docs/tools-and-code.md). The snippet must not raise, must not
contain '{{' or '}}', and can import only json, re and datetime. A builder writes only the brief-specific part (the
body). This module puts the helpers in front of it, checks the rules, and runs it locally on sample variables
before it goes to the platform.

    python lib/pycode.py run <file with the body> <sample vars json>     # runs helpers + body, prints the new vars
    python lib/pycode.py node <name> <file with the body> <next node>    # prints a code node JSON
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spoken

HELPERS = r'''
import datetime, json, re
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def parse_now(v):
    """The call time from the call variable `now` (for example 2026-10-14T11:00). Never the real clock."""
    s = str(v or "").strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s[:19] if "S" in fmt else s[:16] if "M" in fmt else s[:10], fmt)
        except Exception:
            pass
    return None

def to_date(x):
    if isinstance(x, datetime.datetime):
        return x.date()
    if isinstance(x, datetime.date):
        return x
    try:
        return datetime.date.fromisoformat(str(x).strip()[:10])
    except Exception:
        return None

def iso(d):
    return d.isoformat() if d else ""

def spoken(d):
    """Friday 16 October 2026"""
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}" if d else ""

def is_business_day(d, holidays=(), weekend=(5, 6)):
    hs = {str(h)[:10] for h in holidays}
    return d.weekday() not in weekend and d.isoformat() not in hs

def next_business_day(d, holidays=(), weekend=(5, 6), include_today=False):
    x = d if include_today else d + datetime.timedelta(days=1)
    for _ in range(400):
        if is_business_day(x, holidays, weekend):
            return x
        x += datetime.timedelta(days=1)
    return None

def add_business_days(d, n, holidays=(), weekend=(5, 6)):
    """The n-th business day after d (d itself does not count). n = 0 gives d."""
    x, k = d, 0
    while k < n:
        x += datetime.timedelta(days=1)
        if is_business_day(x, holidays, weekend):
            k += 1
    return x

def business_days(start, count, holidays=(), weekend=(5, 6), include_start=True):
    out, x = [], start
    if not include_start:
        x += datetime.timedelta(days=1)
    while len(out) < count:
        if is_business_day(x, holidays, weekend):
            out.append(x)
        x += datetime.timedelta(days=1)
    return out

def week_start(d):
    return d - datetime.timedelta(days=d.weekday())

def weekday_in_week(d, weekday, week_offset=0):
    """The given weekday (0 = Monday) in the calendar week of d, plus week_offset weeks."""
    return week_start(d) + datetime.timedelta(days=weekday + 7 * week_offset)

def last_business_day_of_week(d, week_offset=0, holidays=(), weekend=(5, 6)):
    start = week_start(d) + datetime.timedelta(days=7 * week_offset)
    best = None
    for i in range(7):
        x = start + datetime.timedelta(days=i)
        if is_business_day(x, holidays, weekend):
            best = x
    return best

def last_day_of_month(d):
    nxt = (d.replace(day=28) + datetime.timedelta(days=4))
    return nxt - datetime.timedelta(days=nxt.day)

def money(x):
    """420 -> '420 dollars', 126.5 -> '126.50 dollars'"""
    try:
        f = float(x)
    except Exception:
        return str(x)
    return (f"{f:.0f}" if f == int(f) else f"{f:.2f}") + " dollars"

def as_list(x):
    """A list that came through the variable table: a list, a JSON string, or a Python repr string."""
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        s = x.strip()
        try:
            v = json.loads(s)
            return v if isinstance(v, list) else []
        except Exception:
            pass
        try:
            import ast
            v = ast.literal_eval(s)
            return v if isinstance(v, list) else []
        except Exception:
            return []
    return []

def flat_list(vars, prefix):
    """A list that the engine stored as flattened keys: prefix.0.field, prefix.1.field, ..."""
    rows = {}
    for k, v in vars.items():
        if isinstance(k, str) and k.startswith(prefix + "."):
            rest = k[len(prefix) + 1:].split(".", 1)
            if rest[0].isdigit() and len(rest) == 2:
                rows.setdefault(int(rest[0]), {})[rest[1]] = v
    return [rows[i] for i in sorted(rows)]

def get_list(vars, *names):
    """The first non-empty list among the named variables, in list form or in flattened form."""
    for n in names:
        lst = as_list(vars.get(n))
        if lst:
            return lst
        lst = flat_list(vars, n)
        if lst:
            return lst
    return []

def num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default
'''

FORBIDDEN = ("{{", "}}")


def compose(body):
    """Helpers plus the body, as one snippet. The body runs inside try/except: a code step must never raise."""
    lines = body.rstrip().splitlines() or ["pass"]
    wrapped = "try:\n" + "\n".join("    " + l for l in lines) + "\n    vars['code_status'] = 'ok'\nexcept Exception as e:\n    vars['code_status'] = 'error: ' + str(e)[:200]\n"
    # The spoken value helpers (words_to_number, digits, spoken_date) are there too, for values that come from speech.
    code = HELPERS.strip() + "\n" + spoken.SOURCE.strip() + "\n\n" + wrapped
    for f in FORBIDDEN:
        if f in code:
            raise ValueError(f"the code contains {f!r}: Freya can template it. Write the dict differently (for example dict(a=dict(b=1))).")
    compile(code, "code_step", "exec")
    return code


def run(body, sample_vars):
    """Runs the snippet like the platform does, on a copy of the sample variables. Returns the variables after it."""
    v = dict(sample_vars)
    exec(compose(body), {"vars": v, "__name__": "code_step"})
    return v


def node(name, body, next_node, timeout_ms=10000):
    return {
        "name": name,
        "node_type": "code",
        "passthrough": True,
        "passthrough_default_transition": next_node,
        "on_enter": {"type": "silent"},
        "disable_inactivity_monitor": True,
        "pre_actions": [
            {
                "type": "function",
                "function": {
                    "name": "code_exec",
                    "handler": "__function__:code_exec",
                    "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": compose(body)}, "timeout_ms": {"type": "number", "default": timeout_ms}}},
                },
            }
        ],
        "transitions": [{"target_node": next_node, "description": "always", "condition": {"operator": "always"}}],
    }


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "run":
        out = run(open(a[1]).read(), json.load(open(a[2])))
        print(json.dumps({k: v for k, v in out.items()}, indent=1, default=str))
    elif len(a) >= 4 and a[0] == "node":
        print(json.dumps(node(a[1], open(a[2]).read(), a[3]), indent=1))
    else:
        sys.exit(__doc__)
