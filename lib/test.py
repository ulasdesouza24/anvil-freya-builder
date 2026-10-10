"""Run the practice customers on the published workflow of a slot, and record the result for the tested version.

    python lib/test.py <slot> <run_cases options> --out work/<slot>/run<N>.json

Example: python lib/test.py brief-a --brief A --out work/brief-a/run1.json
         python lib/test.py brief-a --brief A --style pieces --out work/brief-a/run2.json

A simulation runs the version that was published when it started. This command keeps the workflow text from the
start and gives it to lib/snapshot.py, so the result goes to the version that was tested, also when you save a new
version while the test runs. Never stop a test: Freya cannot stop a simulation, and the next test waits until the
stopped one ends.
"""
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
import snapshot  # noqa: E402

KIT = pathlib.Path(os.environ.get("KIT", ROOT / "kit"))


def main():
    a = sys.argv[1:]
    if len(a) < 3 or "--out" not in a:
        sys.exit(__doc__)
    slot, opts = a[0], a[1:]
    out = opts[opts.index("--out") + 1]
    style = opts[opts.index("--style") + 1] if "--style" in opts else None
    state_file = ROOT / ".freya-agents.json"
    state = json.loads(state_file.read_text()).get(slot) if state_file.exists() else None
    wf = ROOT / "work" / slot / "workflow.json"
    if not state or not wf.exists():
        sys.exit(f"no saved workflow for the slot {slot}: save it first")
    # The test runs the published version. A workflow.json written after the last save is not that version.
    if wf.stat().st_mtime > state_file.stat().st_mtime + 1:
        sys.exit("work/<slot>/workflow.json changed after the last save: save and publish it, then start the test")
    text = wf.read_text()
    print(f"test of version {state.get('version')} (agent {state['agent_id']}), options {' '.join(opts)}", flush=True)
    r = subprocess.run([sys.executable, str(KIT / "tools" / "run_cases.py"), state["agent_id"], *opts], cwd=ROOT)
    if not pathlib.Path(out).exists() and not (ROOT / out).exists():
        sys.exit(f"run_cases ended with code {r.returncode} and wrote no result")
    e = snapshot.record(slot, out if pathlib.Path(out).exists() else str(ROOT / out), style, text=text)
    if e is None:
        print("not recorded: no customer got a tool call, so the platform was down. Do not change the workflow: run "
              "lib/platform_check.py, wait, and test again.")
        sys.exit(2)
    print(f"recorded as snapshot version {e['version']}: plain {[(x['passed'], x['total']) for x in e['plain']]} "
          f"style {[(x['passed'], x['total']) for x in e['style']]}")


if __name__ == "__main__":
    main()
