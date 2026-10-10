"""The full rehearsal, from zero, in one command. It waits when Freya or the bank's tool API is down.

    python3 rehearsal/run_all.py [--kit ~/Desktop/freya-kit/build-the-builder] [--only a,b,raw]

Steps (each build uses a new slot, so nothing of an earlier run mixes in):
  a    build Brief A (test A), then 3 runs of each practice customer, then one run in each hard customer style
  b    build Brief A + B (test B), then 3 runs of each Brief B customer
  raw  build the raw-material version of Brief A (rehearsal/brief-a-raw.md, test A), then 3 runs of each customer
The summary is results/rehearsal-<start>/summary.md. A customer counts only with 3 passes out of 3, as in the final.
"""
import argparse, json, os, pathlib, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
STYLES = ["pieces", "corrects", "talkative", "asks_back", "in_words"]


def log(out, text):
    line = f"{time.strftime('%H:%M:%S')} {text}"
    print(line, flush=True)
    with open(out / "progress.log", "a") as f:
        f.write(line + "\n")


def services_up(kit, probe_workflow):
    # Simulations do not need the chat route (it gave 504 while simulations ran): check the tool API only.
    r = subprocess.run([sys.executable, "lib/platform_check.py", probe_workflow, str(kit / "tools" / "openapi.json"), "--tool-only"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip().replace("\n", " | ")


def wait_up(out, kit, probe_workflow):
    """Wait until the tool API is up and no simulation runs: a build must not lose its time budget in the queue."""
    sys.path.insert(0, str(ROOT / "lib"))
    import sim_queue

    for i in range(60):
        ok, msg = services_up(kit, probe_workflow)
        if ok:
            sim_queue.wait_empty(say=lambda t: log(out, t), every=30)
            return
        log(out, f"waiting: {msg}")
        time.sleep(180)
    raise SystemExit("the services stayed down for 3 hours")


def build(out, kit, slot, files, test):
    log(out, f"build {slot}: {[pathlib.Path(f).name for f in files]} test={test}")
    t0 = time.time()
    r = subprocess.run([sys.executable, "build.py", *map(str, files), str(kit / "tools" / "openapi.json"), "--slot", slot, "--test", test, "--minutes", "28"], cwd=ROOT, capture_output=True, text=True)
    (out / f"build-{slot}.log").write_text(r.stdout + r.stderr)
    tests = [l.split("test", 1)[1].strip() for l in r.stdout.splitlines() if " test " in l and "passed" in l]
    best = [l.split("best", 1)[1].strip() for l in r.stdout.splitlines() if " best " in l]
    log(out, f"build {slot} done in {time.time() - t0:.0f} s, exit {r.returncode}, tests {[t.split(' passed')[0] for t in tests]}, best {best[-1] if best else '-'}")
    state = json.loads((ROOT / ".freya-agents.json").read_text())
    return state[slot]["agent_id"], {"seconds": round(time.time() - t0), "tests": [t.split(" passed")[0] for t in tests], "best": best[-1] if best else ""}


def run_cases(out, kit, probe_workflow, agent, brief, name, reps=1, style=None):
    """One run_cases call. A run that is an outage (no customer got a tool call) waits and runs again, once."""
    sys.path.insert(0, str(ROOT / "lib"))
    import snapshot

    for attempt in (1, 2):
        wait_up(out, kit, probe_workflow)
        dst = out / f"{name}.json"
        cmd = [sys.executable, "kit/tools/run_cases.py", agent, "--brief", brief, "--reps", str(reps), "--out", str(dst)] + (["--style", style] if style else [])
        # The log is written while the run goes on, so the trace screen can show it.
        with open(out / f"{name}.log", "w") as f:
            subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, text=True)
        res = json.loads(dst.read_text()) if dst.exists() else {}
        if res and not snapshot.outage(res):
            per = {row["id"]: f"{row['passes']}/{row['runs']}" for row in res.get("final", [])}
            log(out, f"{name}: {res.get('passed')}/{res.get('total')} {per if reps > 1 else ''}")
            return {"passed": res.get("passed"), "total": res.get("total"), "per_customer": per}
        log(out, f"{name}: outage or no result (attempt {attempt}), waiting")
    return {"passed": None, "total": None, "per_customer": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=os.path.expanduser("~/Desktop/freya-kit/build-the-builder"))
    ap.add_argument("--only", default="a,b,raw")
    ap.add_argument("--probe", default="ed036ff6-6c55-472d-9fa4-831b6afc7bb6", help="a workflow for the chat check")
    a = ap.parse_args()
    kit = pathlib.Path(a.kit)
    stamp = time.strftime("%Y%m%d-%H%M")
    out = ROOT / "results" / f"rehearsal-{stamp}"
    out.mkdir(parents=True)
    steps = a.only.split(",")
    summary = {}
    if "a" in steps:
        wait_up(out, kit, a.probe)
        agent, b = build(out, kit, f"rh-a-{stamp}", [kit / "briefs" / "brief-a.md"], "A")
        summary["A build"] = b
        summary["A 3 runs"] = run_cases(out, kit, a.probe, agent, "A", "a-reps3", reps=3)
        for st in STYLES:
            summary[f"A style {st}"] = run_cases(out, kit, a.probe, agent, "A", f"a-{st}", style=st)
    if "b" in steps:
        wait_up(out, kit, a.probe)
        agent, b = build(out, kit, f"rh-b-{stamp}", [kit / "briefs" / "brief-a.md", kit / "briefs" / "brief-b.md"], "B")
        summary["B build"] = b
        summary["B 3 runs"] = run_cases(out, kit, a.probe, agent, "B", "b-reps3", reps=3)
    if "raw" in steps:
        wait_up(out, kit, a.probe)
        agent, b = build(out, kit, f"rh-raw-{stamp}", [ROOT / "rehearsal" / "brief-a-raw.md"], "A")
        summary["raw build"] = b
        summary["raw 3 runs"] = run_cases(out, kit, a.probe, agent, "A", "raw-reps3", reps=3)
    lines = ["# Rehearsal " + stamp, "", "| Step | Result |", "|---|---|"]
    for k, v in summary.items():
        if "build" in k:
            lines.append(f"| {k} | {v['seconds']} s, tests {v['tests']}, {v['best']} |")
        else:
            lines.append(f"| {k} | {v['passed']}/{v['total']} {v['per_customer'] if v['per_customer'] and len(v['per_customer']) <= 13 and 'runs' in k else ''} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
