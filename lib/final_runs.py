"""Run the builder several times on the final brief, one run after the other, and compare the runs.

    python3 lib/final_runs.py <brief.md> [<more briefs>] <tool API.json> [--runs 4] [--last-start 22:25] [--prefix hidden]

Each run is a normal builder run (`python3 build.py ... --slot <prefix>-r<N>`), with its own trace. No run starts
after --last-start (local time). After each run it prints lib/compare_runs.py for all finished runs, and at the end a
proposal: the run with an export, no error line, the fewest static check errors, the fewest open review items, and
the shortest build time, in this order. Choose with RUNBOOK.md ("Choose the run to submit"): a chat check comes
before the copy to the submission names.
"""
import argparse, datetime, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))


def facts(slot, api):
    import compare_runs

    trace = ROOT / "submission" / f"{slot}.trace.log"
    wf = ROOT / "submission" / f"{slot}.workflow.json"
    text = trace.read_text() if trace.exists() else ""
    errors = sum(1 for l in text.splitlines() if re.search(r"s error\s", l))
    end = re.search(r" end\s+\d+ model calls, (\d+) s", text)
    checks = 99
    if wf.exists():
        # The export from Freya adds agent_config, which the static check flags: check the builder's own file.
        own = ROOT / "work" / slot / "workflow.json"
        r = subprocess.run([sys.executable, str(ROOT / "lib" / "check_workflow.py"), str(own if own.exists() else wf)] + (["--openapi", api] if api else []), capture_output=True, text=True)
        m = re.search(r"(\d+) error", r.stdout + r.stderr)
        checks = int(m.group(1)) if m else 99
    rev = compare_runs.review_counts(slot) or {"open": 99}
    return {"slot": slot, "export": wf.exists(), "errors": errors, "checks": checks, "open": rev.get("open", 99),
            "seconds": int(end.group(1)) if end else 99999}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--last-start", default="22:25")
    ap.add_argument("--prefix", default="hidden")
    ap.add_argument("--minutes", default="28")
    a = ap.parse_args()
    api = next((f for f in a.files if f.endswith(".json")), None)
    hh, mm = map(int, a.last_start.split(":"))
    done = []
    for i in range(1, a.runs + 1):
        now = datetime.datetime.now()
        if (now.hour, now.minute) > (hh, mm):
            print(f"{now:%H:%M}: no new run after {a.last_start}", flush=True)
            break
        slot = f"{a.prefix}-r{i}"
        subprocess.run([sys.executable, str(ROOT / "lib" / "sim_queue.py"), "--cancel-stuck", "30"], cwd=ROOT)
        print(f"{datetime.datetime.now():%H:%M} start {slot}", flush=True)
        (ROOT / "traces").mkdir(exist_ok=True)
        with open(ROOT / "traces" / f"{slot}.console.log", "w") as f:
            subprocess.run([sys.executable, "build.py", *a.files, "--slot", slot, "--minutes", a.minutes], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        done.append(slot)
        print(f"{datetime.datetime.now():%H:%M} end {slot}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "lib" / "compare_runs.py"), *done] + (["--openapi", api] if api else []), cwd=ROOT)
    rows = [facts(s, api) for s in done]
    ok = [r for r in rows if r["export"] and r["errors"] == 0] or [r for r in rows if r["export"]]
    if not ok:
        print("PROPOSAL: no run has an export. See RUNBOOK.md (After each run, step 4: --export-only).")
        return
    best = min(ok, key=lambda r: (r["checks"], r["open"], r["seconds"]))
    print("runs:", rows)
    print(f"PROPOSAL: {best['slot']} (export, {best['errors']} error lines, {best['checks']} static check errors, "
          f"{best['open']} open review items, {best['seconds']} s). Do the chat check, then copy it (RUNBOOK.md).")


if __name__ == "__main__":
    main()
