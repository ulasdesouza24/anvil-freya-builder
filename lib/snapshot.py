"""Keep each tested version of a workflow, so that the best one is the result (the Anvil evolve rule: a change that
makes the agent worse is not kept).

    python lib/snapshot.py record <slot> <run_cases --out json> [--style <name>]   # after each test (lib/test.py does it)
    python lib/snapshot.py best <slot>                                              # prints the best version

`record` copies the tested workflow to work/<slot>/versions/v<N>.json and adds the result to
work/<slot>/history.json. A simulation runs the version that was published when it started, so lib/test.py gives
the workflow text from the start of the test. Without it, `record` uses work/<slot>/workflow.json. The best version has the most passes on plain runs (no --style), then the most passes on
style runs, then the later version.
"""
import json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def history_path(slot):
    return ROOT / "work" / slot / "history.json"


def load(slot):
    p = history_path(slot)
    return json.loads(p.read_text()) if p.exists() else []


def outage(run):
    """A run where no customer got one tool call and none passed: the platform was down, not the agent."""
    rows = run.get("all_rows") or run.get("rows") or []
    rows = [x for r in rows for x in (r if isinstance(r, list) else [r])]
    return bool(rows) and not run.get("passed") and all(not r.get("tools") for r in rows if isinstance(r, dict))


def record(slot, run_file, style=None, text=None, platform_up=False):
    hist = load(slot)
    run = json.loads(pathlib.Path(run_file).read_text())
    # A run that looks like an outage while the platform check says up is the agent's own failure: it counts.
    if outage(run) and not platform_up:
        return None
    text = text if text is not None else (ROOT / "work" / slot / "workflow.json").read_text()
    # A test of the same workflow as the last snapshot adds to that version.
    same = next((h for h in reversed(hist) if (ROOT / h["file"]).exists() and (ROOT / h["file"]).read_text() == text), None)
    if same is None:
        n = len({h["version"] for h in hist}) + 1
        dst = ROOT / "work" / slot / "versions" / f"v{n}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
        entry = {"version": n, "file": str(dst.relative_to(ROOT)), "plain": [], "style": [], "at": time.time()}
        hist.append(entry)
    else:
        entry = same
    entry["style" if style else "plain"].append({"passed": run.get("passed"), "total": run.get("total"), "style": style, "run": str(run_file)})
    history_path(slot).write_text(json.dumps(hist, indent=1))
    return entry


def score(entry):
    plain = [r["passed"] / r["total"] for r in entry["plain"] if r.get("total")]
    style = [r["passed"] / r["total"] for r in entry["style"] if r.get("total")]
    # The weakest plain run counts: the score needs the agent to pass every time.
    return (min(plain) if plain else -1, min(style) if style else -1, entry["version"])


def best(slot):
    hist = [h for h in load(slot) if h["plain"] or h["style"]]
    return max(hist, key=score) if hist else None


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "record":
        style = a[a.index("--style") + 1] if "--style" in a else None
        e = record(a[1], a[2], style)
        if e is None:
            sys.exit("not recorded: no customer got a tool call, so the platform was down. Do not change the workflow: run lib/platform_check.py, wait, and test again.")
        print(f"version {e['version']}: plain {[(r['passed'], r['total']) for r in e['plain']]} style {[(r['passed'], r['total']) for r in e['style']]}")
    elif len(a) >= 2 and a[0] == "best":
        b = best(a[1])
        print(json.dumps(b, indent=1) if b else "no tested version")
    else:
        sys.exit(__doc__)
