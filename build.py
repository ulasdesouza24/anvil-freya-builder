"""Anvil's Freya builder: a brief in, a phone agent (a Freya workflow) out.

    python build.py <brief.md> [<more briefs>] [--openapi tools/openapi.json] [--slot name] [--test A|B|none] [--minutes 28]

One command, no manual step. Claude (through the Claude Agent SDK and the user's login) works as the builder,
with the skills in .claude/skills and the tested helpers in lib/:
  1. reads the brief(s) and the tool API, and writes a rule ledger and a policy spec (every rule, numbered);
  2. writes the workflow: tools from the OpenAPI file with result hooks, code steps for dates and numbers that run
     locally first, routes on tool results;
  3. checks it (static checks, a dry run on the platform), saves and publishes it, and talks to it in chat;
  4. when practice customers exist for the brief (--test A or B), runs them and fixes what fails;
  5. checks that every rule of the ledger has a place in the workflow.
At the end it exports the workflow to out/<slot>.workflow.json. The trace of the run is traces/<start>-<slot>.log
(start, end, each model call with its model and purpose, what was created on Freya, each test) and the full message
log is traces/<start>-<slot>.jsonl.

Needs FREYA_API_KEY and FREYA_BANK_TEAM_KEY (source the kit's env.sh), and a Claude login.
"""
import argparse, asyncio, dataclasses, json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
KIT = pathlib.Path(os.environ.get("KIT", os.path.expanduser("~/Desktop/freya-kit/build-the-builder"))).resolve()
sys.path.insert(0, str(KIT))


class Trace:
    """The trace that the rules ask for: plain text, one event per line, and the full message log next to it."""

    def __init__(self, slot):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (HERE / "traces").mkdir(exist_ok=True)
        self.text = (HERE / "traces" / f"{stamp}-{slot}.log").open("w")
        self.jsonl = (HERE / "traces" / f"{stamp}-{slot}.jsonl").open("w")
        self.t0 = time.time()
        self.calls = 0

    def line(self, kind, text):
        s = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} +{time.time() - self.t0:6.0f}s {kind:<8} {text}"
        self.text.write(s + "\n")
        self.text.flush()
        print(s, flush=True)

    def raw(self, obj):
        self.jsonl.write(json.dumps(obj, default=str) + "\n")
        self.jsonl.flush()


def purpose_of(message):
    """One line about what a model call did: its first sentence, or the tools it called."""
    from claude_agent_sdk import TextBlock, ToolUseBlock

    texts, tools = [], []
    for b in message.content:
        if isinstance(b, TextBlock) and b.text.strip():
            texts.append(" ".join(b.text.split())[:160])
        elif isinstance(b, ToolUseBlock):
            inp = b.input or {}
            what = inp.get("description") or inp.get("command") or inp.get("file_path") or inp.get("skill") or ""
            tools.append(f"{b.name}({' '.join(str(what).split())[:110]})")
    return "; ".join(texts[:1] + tools) or "(no text)"


def created_from(message, trace):
    """Freya objects that a tool result reports: a saved workflow, a simulation, a run summary."""
    from claude_agent_sdk import ToolResultBlock

    for b in getattr(message, "content", []) or []:
        if isinstance(b, ToolResultBlock):
            text = b.content if isinstance(b.content, str) else json.dumps(b.content, default=str)
            if '"workflow_id"' in text and '"agent_id"' in text:
                trace.line("created", " ".join(text.split())[:300])
            for key in ("passed (bank records", "PASS ", "FAIL "):
                if key in text:
                    for l in text.splitlines():
                        if l.startswith(("PASS", "FAIL")) or "passed (bank records" in l:
                            trace.line("test", l.strip()[:240])
                    break


async def run_builder(args, trace):
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, UserMessage, query

    deadline = time.time() + args.minutes * 60
    options = ClaudeAgentOptions(
        cwd=str(HERE),
        model=args.model,
        skills=["build-freya-agent"],
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        permission_mode="dontAsk",
        max_turns=200,
        add_dirs=[str(KIT)],
        env={
            "BASH_DEFAULT_TIMEOUT_MS": "900000",
            "BASH_MAX_TIMEOUT_MS": "1200000",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "KIT": str(KIT),
            "BUILD_DEADLINE": str(int(deadline)),
        },
    )
    briefs = [str(pathlib.Path(b).resolve()) for b in args.briefs]
    prompt = (
        f"Use the build-freya-agent skill. Build the phone agent for these brief files, in this order: {' '.join(briefs)}.\n"
        f"Tool API file: {pathlib.Path(args.openapi).resolve()}.\nSlot: {args.slot}.\n"
        f"Practice customers: {'run them with --brief ' + args.test if args.test != 'none' else 'none exist for this brief: do not run tools/run_cases.py'}.\n"
        f"Kit folder: {KIT}.\nTime budget: you must be done before the Unix time {int(deadline)} "
        f"({args.minutes} minutes). Check the time with `date +%s` before you start a test."
    )
    trace.line("start", f"briefs={args.briefs} openapi={args.openapi} slot={args.slot} test={args.test} model={args.model} budget={args.minutes}min")

    async def consume():
        async for message in query(prompt=prompt, options=options):
            trace.raw({"type": type(message).__name__, **(dataclasses.asdict(message) if dataclasses.is_dataclass(message) else {"repr": repr(message)})})
            if isinstance(message, AssistantMessage):
                trace.calls += 1
                trace.line("model", f"{getattr(message, 'model', args.model)} | {purpose_of(message)}")
            elif isinstance(message, UserMessage):
                created_from(message, trace)
            elif isinstance(message, ResultMessage):
                trace.line("result", f"{message.num_turns} turns, {message.duration_ms / 1000:.0f} s, reported cost ${message.total_cost_usd or 0:.2f}")

    try:
        await asyncio.wait_for(consume(), timeout=max(60, deadline - time.time()))
    except asyncio.TimeoutError:
        trace.line("timeout", "the time budget ended: the last saved workflow is the result")


def finish(args, trace):
    """Export the workflow of the slot, as the submission needs it."""
    import freya

    state = json.loads((HERE / ".freya-agents.json").read_text()) if (HERE / ".freya-agents.json").exists() else {}
    ids = state.get(args.slot)
    if not ids:
        trace.line("error", f"no workflow was saved for the slot {args.slot}")
        return 1
    out = HERE / "out" / f"{args.slot}.workflow.json"
    out.parent.mkdir(exist_ok=True)
    freya.export_workflow(ids["workflow_id"], str(out))
    trace.line("export", f"workflow_id={ids['workflow_id']} agent_id={ids.get('agent_id')} -> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("briefs", nargs="+")
    ap.add_argument("--openapi", default=str(KIT / "tools" / "openapi.json"))
    ap.add_argument("--slot")
    ap.add_argument("--test", choices=["A", "B", "none"], default="none")
    ap.add_argument("--minutes", type=float, default=28)
    ap.add_argument("--model", default=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"))
    args = ap.parse_args()
    args.slot = args.slot or pathlib.Path(args.briefs[-1]).stem
    for k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY"):
        if not os.environ.get(k):
            sys.exit(f"{k} is not set: source the kit's env.sh first")
    trace = Trace(args.slot)
    try:
        asyncio.run(run_builder(args, trace))
        code = finish(args, trace)
    finally:
        trace.line("end", f"{trace.calls} model calls, {time.time() - trace.t0:.0f} s")
    sys.exit(code)


if __name__ == "__main__":
    main()
