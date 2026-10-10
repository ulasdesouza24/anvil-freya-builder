"""A short, readable story of one Freya call: what was said, which node, which tool with which arguments and result,
and why each route fired or did not.

    python lib/analyze_call.py <call_id> [--vars name1,name2]     # needs the kit's freya.py on the path (env KIT)
    python lib/analyze_call.py --run results/run.json             # every failed call of a run_cases output

docs/api.md: messages of role "system" hold engine events (node_enter, function_call_start, function_call_complete,
route_evaluated, error). The route event has the result of every condition and the variable table.
"""
import json, os, sys

KIT = os.environ.get("KIT", os.path.expanduser("~/Desktop/freya-kit/build-the-builder"))
sys.path.insert(0, KIT)


def short(x, n=220):
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 3] + "..."


def story(call, want_vars=()):
    out = []
    for m in call.get("messages", []):
        role, msg, node = m.get("role"), m.get("message"), m.get("nodeId")
        t = m.get("secondsFromStart")
        ts = f"{t:5.0f}s" if isinstance(t, (int, float)) else "     "
        if role in ("assistant", "user", "bot"):
            out.append(f"{ts} {('AGENT' if role != 'user' else 'USER '):5} [{node or ''}] {short(msg, 400)}")
            continue
        if role != "system":
            continue
        try:
            ev = json.loads(msg) if isinstance(msg, str) else (msg or {})
        except Exception:
            out.append(f"{ts} SYS   {short(msg)}")
            continue
        kind = ev.get("event") or ev.get("type")
        if kind == "node_enter":
            out.append(f"{ts} ->    enter {ev.get('node')} (from {ev.get('from_node')}, {short(ev.get('reason') or '', 80)})")
        elif kind == "function_call_start":
            args = ev.get("args") or {}
            body = args.get("body", args) if isinstance(args, dict) else args
            out.append(f"{ts} CALL  {ev.get('function')} {short(body, 260)}")
        elif kind == "function_call_complete":
            res = ev.get("result") or {}
            data = res.get("data", res) if isinstance(res, dict) else res
            out.append(f"{ts} RES   {ev.get('function')} {short(data, 300)}")
        elif kind == "route_evaluated":
            br = ev.get("branches") or []
            fired = [b for b in br if b.get("result") or b.get("matched")]
            line = f"{ts} ROUTE {ev.get('from_node')} -> {ev.get('target') or '(stay)'} matched={ev.get('matched')}"
            if fired:
                line += " by " + short([{k: b.get(k) for k in ('variable', 'operator', 'operand', 'value', 'description') if b.get(k) is not None} for b in fired], 200)
            out.append(line)
            vt = ev.get("variable_table") or {}
            for v in want_vars:
                if v in vt:
                    val = vt[v].get("value") if isinstance(vt[v], dict) else vt[v]
                    out.append(f"          {v} = {short(val, 120)}")
        elif kind == "error":
            out.append(f"{ts} ERROR {short(ev.get('message'))} {short(ev.get('details') or '', 160)}")
    out.append(f"ended: {call.get('endedReason')}")
    return "\n".join(out)


if __name__ == "__main__":
    import freya  # the kit client

    a = sys.argv[1:]
    want = a[a.index("--vars") + 1].split(",") if "--vars" in a else []
    if a and a[0] == "--run":
        run = json.load(open(a[1]))
        rows = run.get("rows") or run.get("results") or run
        for r in rows if isinstance(rows, list) else []:
            if r.get("pass") or not r.get("call_id"):
                continue
            print(f"\n===== {r.get('id')}: {' | '.join(r.get('failed', []))[:400]}")
            print(story(freya.get_call(r["call_id"]), want))
    elif a:
        print(story(freya.get_call(a[0]), want))
    else:
        sys.exit(__doc__)
