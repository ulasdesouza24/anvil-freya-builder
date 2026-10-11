"""Compare two or more builder runs of the same brief, to choose the one to submit.

    python lib/compare_runs.py <slot> <slot> [...] --openapi <tool API file>

For each slot it prints what can be checked without practice customers:
  - the end of the run: an export, and no "error" line in the trace,
  - the static check of the exported workflow (lib/check_workflow.py): the number of errors,
  - the review (work/<slot>/review.md): items marked OK, FIXED, N/A, and items with no mark (open),
  - the build time (equal scores are ranked by the shorter build time).
It reads files only. Choose with RUNBOOK.md ("Choose the run to submit").
"""
import pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def review_counts(slot):
    p = ROOT / "work" / slot / "review.md"
    if not p.exists():
        return None
    marks = {"OK": 0, "FIXED": 0, "N/A": 0, "open": 0}
    for line in p.read_text().splitlines():
        m = re.match(r"\s*(?:[-*]\s*)?(?:\*\*)?(\d+)[.)]", line)
        if not m:
            continue
        mark = next((k for k in ("FIXED", "N/A", "OK") if re.search(rf"\b{re.escape(k)}\b", line)), "open")
        marks[mark] += 1
    return marks


def main():
    a = sys.argv[1:]
    api = a[a.index("--openapi") + 1] if "--openapi" in a else None
    slots = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--openapi")]
    if not slots:
        sys.exit(__doc__)
    for slot in slots:
        trace = ROOT / "submission" / f"{slot}.trace.log"
        wf = ROOT / "submission" / f"{slot}.workflow.json"
        text = trace.read_text() if trace.exists() else ""
        errors = [l for l in text.splitlines() if re.search(r"s error\s", l)]
        end = re.search(r" end\s+(\d+) model calls, (\d+) s", text)
        check = "no export"
        if wf.exists():
            # The export from Freya adds agent_config, which the static check flags: check the builder's own file.
            own = ROOT / "work" / slot / "workflow.json"
            r = subprocess.run([sys.executable, str(ROOT / "lib" / "check_workflow.py"), str(own if own.exists() else wf)] + (["--openapi", api] if api else []),
                               capture_output=True, text=True)
            m = re.search(r"(\d+) error", r.stdout + r.stderr)
            check = f"{m.group(1)} errors" if m else (r.stdout + r.stderr).strip()[-80:]
        print(f"{slot}:")
        print(f"  export: {'yes' if wf.exists() else 'NO'} | error lines in trace: {len(errors)}")
        for l in errors[:3]:
            print(f"    {l[:160]}")
        print(f"  static check: {check}")
        print(f"  review: {review_counts(slot) or 'no review.md'}")
        print(f"  build time: {end.group(2) + ' s' if end else 'no end line'}")


if __name__ == "__main__":
    main()
