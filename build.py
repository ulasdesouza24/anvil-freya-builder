"""Anvil's Freya builder: a brief in, a phone agent (a Freya workflow) out.

    python3 build.py <brief.md> [<more briefs>] <tool API file.json> [--slot name] [--test A|B|none] [--minutes 28]

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
import argparse, asyncio, dataclasses, json, os, pathlib, shutil, signal, sys, time

HERE = pathlib.Path(__file__).resolve().parent
# The public files of the hackathon kit, copied by setup_kit.sh. The builder works only inside its own folder.
KIT = pathlib.Path(os.environ.get("KIT", HERE / "kit")).resolve()
sys.path.insert(0, str(KIT))


# What the builder may test on. The expected records of a practice customer follow the rules of its own brief: Brief A
# never adds a note, and Brief B adds one for each product without a promise. So a Brief B build tests only on the
# customers of Brief B.
PRACTICE = {
    "A": "run them with `--brief A`",
    "B": "run them with `--brief B` (the customers of Brief A expect the rules of Brief A alone, so they do not apply)",
    "none": "none exist for this brief: do not run lib/test.py or kit/tools/run_cases.py. The review of step 7b is your test: do it in full, and use the time that is left for it",
}


SECRET_ENV = ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")


def redact(text):
    """The trace is committed: no key value may be in it."""
    for k in SECRET_ENV:
        v = os.environ.get(k)
        if v and len(v) >= 8:
            text = text.replace(v, f"<{k}>")
    return text


class Trace:
    """The trace that the rules ask for: plain text, one event per line, and the full message log next to it.

    The text trace goes to traces/<start>-<slot>.log and to submission/<slot>.trace.log (the file to commit)."""

    def __init__(self, slot):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (HERE / "traces").mkdir(exist_ok=True)
        (HERE / "submission").mkdir(exist_ok=True)
        self.texts = [(HERE / "traces" / f"{stamp}-{slot}.log").open("w"), (HERE / "submission" / f"{slot}.trace.log").open("w")]
        self.jsonl = (HERE / "traces" / f"{stamp}-{slot}.jsonl").open("w")
        self.t0 = time.time()
        self.calls = 0

    def line(self, kind, text):
        s = redact(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} +{time.time() - self.t0:6.0f}s {kind:<8} {text}")
        for f in self.texts:
            f.write(s + "\n")
            f.flush()
        print(s, flush=True)

    def raw(self, obj):
        self.jsonl.write(redact(json.dumps(obj, default=str)) + "\n")
        self.jsonl.flush()


def purpose_of(blocks):
    """One line about what a model call did: its first sentence, and the tools it called."""
    from claude_agent_sdk import TextBlock, ToolUseBlock

    texts, tools = [], []
    for b in blocks:
        if isinstance(b, TextBlock) and b.text.strip():
            texts.append(" ".join(b.text.split())[:160])
        elif isinstance(b, ToolUseBlock):
            inp = b.input or {}
            what = inp.get("description") or inp.get("command") or inp.get("file_path") or inp.get("skill") or ""
            tools.append(f"{b.name}({' '.join(str(what).split())[:110]})")
    return "; ".join(texts[:1] + tools) or "thinks about the next step"


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
        env={
            "BASH_DEFAULT_TIMEOUT_MS": "900000",
            "BASH_MAX_TIMEOUT_MS": "1200000",
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "KIT": str(KIT),
            "BUILD_DEADLINE": str(int(deadline)),
        },
    )
    # The inputs go into the work folder: the builder reads nothing outside its own folder.
    inp = HERE / "work" / args.slot / "input"
    if inp.exists():
        shutil.rmtree(inp)
    inp.mkdir(parents=True)
    briefs = []
    for i, b in enumerate(args.briefs, 1):
        dst = inp / f"{i}-{pathlib.Path(b).name}"
        shutil.copy(b, dst)
        briefs.append(str(dst.relative_to(HERE)))
    api_file = inp / "openapi.json"
    shutil.copy(args.openapi, api_file)
    trace.line("input", f"briefs {briefs}, tool API {api_file.relative_to(HERE)}")
    prompt = (
        f"Use the build-freya-agent skill. Build the phone agent for these brief files, in this order: {' '.join(briefs)}.\n"
        f"Tool API file: {api_file.relative_to(HERE)}.\nSlot: {args.slot}.\n"
        f"Practice customers: {PRACTICE[args.test]}.\n"
        "Write all your messages, files and comments in English: they are part of the trace that we submit.\n"
        f"Kit folder: {KIT.relative_to(HERE) if KIT.is_relative_to(HERE) else KIT}. Work only inside the builder folder.\nTime budget: you must be done before the Unix time {int(deadline)} "
        f"({args.minutes} minutes). Check the time with `date +%s` before you start a test."
    )
    trace.line("start", f"briefs={args.briefs} openapi={args.openapi} slot={args.slot} test={args.test} model={args.model} budget={args.minutes}min")

    # The SDK gives one message for each content block (thinking, text, tool use) of a model call. They share a
    # message id: the trace writes one line for each model call, when the call is complete.
    pending = {"id": None, "model": None, "blocks": []}

    def flush():
        if pending["blocks"]:
            trace.calls += 1
            trace.line("model", f"{pending['model']} | {purpose_of(pending['blocks'])}")
        pending.update(id=None, model=None, blocks=[])

    async def consume():
        async for message in query(prompt=prompt, options=options):
            trace.raw({"type": type(message).__name__, **(dataclasses.asdict(message) if dataclasses.is_dataclass(message) else {"repr": repr(message)})})
            if isinstance(message, AssistantMessage):
                mid = getattr(message, "message_id", None) or id(message)
                if mid != pending["id"]:
                    flush()
                    pending.update(id=mid, model=getattr(message, "model", None) or args.model)
                pending["blocks"].extend(message.content)
                continue
            flush()
            if isinstance(message, UserMessage):
                created_from(message, trace)
            elif isinstance(message, ResultMessage):
                trace.line("result", f"{message.num_turns} turns, {message.duration_ms / 1000:.0f} s, reported cost ${message.total_cost_usd or 0:.2f}")
        flush()

    try:
        await asyncio.wait_for(consume(), timeout=max(60, deadline - time.time()))
    except asyncio.TimeoutError:
        flush()
        trace.line("timeout", "the time budget ended: the last saved workflow is the result")


def finish(args, trace):
    """Export the workflow of the slot, as the submission needs it."""
    import freya

    state = json.loads((HERE / ".freya-agents.json").read_text()) if (HERE / ".freya-agents.json").exists() else {}
    ids = state.get(args.slot)
    if not ids:
        trace.line("error", f"no workflow was saved for the slot {args.slot}")
        return 1
    # The result is the best tested version, not the last one (lib/snapshot.py): a late change can make it worse.
    sys.path.insert(0, str(HERE / "lib"))
    import snapshot

    best = snapshot.best(args.slot)
    current = HERE / "work" / args.slot / "workflow.json"
    if best:
        trace.line("best", f"version {best['version']}: plain {[(r['passed'], r['total']) for r in best['plain']]} style {[(r['passed'], r['total']) for r in best['style']]}")
        best_text = (HERE / best["file"]).read_text()
        if not current.exists() or current.read_text() != best_text:
            freya.save_workflow(args.slot, json.loads(best_text), state_file=str(HERE / ".freya-agents.json"))
            current.write_text(best_text)
            trace.line("restore", f"the last version was worse or not tested: saved and published version {best['version']} again")
    out = HERE / "submission" / f"{args.slot}.workflow.json"
    out.parent.mkdir(exist_ok=True)
    freya.export_workflow(ids["workflow_id"], str(out))
    wf = json.loads(out.read_text()).get("workflow", {})
    nodes = wf.get("nodes") or {}
    tools = sorted({t.get("function", {}).get("name") for n in nodes.values() for t in (n.get("tools") or []) + (n.get("pre_actions") or [])} - {None})
    trace.line("created", f"workflow_id={ids['workflow_id']} agent_id={ids.get('agent_id')} steps={len(nodes)} tools={len(tools)} ({', '.join(tools)})")
    trace.line("export", f"{out.relative_to(HERE)}")
    shutil.copy(out, HERE / "out" / out.name) if (HERE / "out").exists() else None
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="the brief file(s), in order, then the tool API file (.json)")
    ap.add_argument("--openapi", help="the tool API file, when it is not given as the last file")
    ap.add_argument("--slot")
    ap.add_argument("--test", choices=["A", "B", "none"], default="none")
    ap.add_argument("--minutes", type=float, default=28)
    ap.add_argument("--model", default=os.environ.get("BUILDER_MODEL", "claude-opus-5-5"))
    args = ap.parse_args()
    args.briefs = [f for f in args.files if not f.endswith(".json")]
    jsons = [f for f in args.files if f.endswith(".json")]
    args.openapi = args.openapi or (jsons[-1] if jsons else None)
    if not args.briefs or not args.openapi:
        sys.exit("give the brief file(s) and the tool API file (.json)")
    args.slot = args.slot or pathlib.Path(args.briefs[-1]).stem
    for k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY"):
        if not os.environ.get(k):
            sys.exit(f"{k} is not set: source the kit's env.sh first")
    trace = Trace(args.slot)
    # The builder session runs as a child process. When this command stops (a signal, an error), its children stop
    # too: an orphan session would go on changing the workflow.
    try:
        os.setpgrp()
    except Exception:
        pass

    def stop_children(signum=None, frame=None):
        trace.line("stop", f"signal {signum}: the builder session stops")
        try:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            os.killpg(0, signal.SIGTERM)
        except Exception:
            pass
        sys.exit(1)

    signal.signal(signal.SIGTERM, stop_children)
    signal.signal(signal.SIGINT, stop_children)
    signal.signal(signal.SIGHUP, stop_children)
    try:
        asyncio.run(run_builder(args, trace))
        code = finish(args, trace)
    finally:
        trace.line("end", f"{trace.calls} model calls, {time.time() - trace.t0:.0f} s")
    sys.exit(code)


if __name__ == "__main__":
    main()
