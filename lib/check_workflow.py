"""Static checks of a Freya workflow before it goes to the platform.

    python lib/check_workflow.py out/brief-a.workflow.json [--openapi tools/openapi.json]

Each rule comes from the kit documents (docs/workflow-format.md, docs/tools-and-code.md). The platform drops
many of these faults without an error, so a broken workflow can save, start, and fail only in a call.
Exit code 1 when there is an error. Warnings do not fail.
"""
import json, re, sys

NODE_TYPES = {"conversation", "api_request", "code", "end_call"}
DET_OPS = {"equals", "not_equals", "greater_than", "less_than", "contains", "is_set", "is_not_set"}


def walk_nulls(v, path, out):
    if v is None:
        out.append(f"{path}: null value (the schema rejects null: leave the field out or use \"\")")
    elif isinstance(v, dict):
        for k, x in v.items():
            walk_nulls(x, f"{path}.{k}", out)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            walk_nulls(x, f"{path}[{i}]", out)


def conditions(cond):
    """All leaf conditions of a condition object."""
    if not isinstance(cond, dict):
        return []
    if "conditions" in cond:
        out = []
        for c in cond.get("conditions") or []:
            out += conditions(c)
        return out
    return [cond]


def tool_names(node):
    return [t.get("function", {}).get("name") for t in node.get("tools") or []]


def check(wf, openapi=None):
    errors, warnings = [], []
    E, W = errors.append, warnings.append
    # The docs say the schema rejects null, but the exported example agent has null fields and saves: a warning.
    walk_nulls(wf, "workflow", warnings)
    if "agent_config" in wf:
        E("agent_config: leave it out (the kit README: a workflow with it can fail to start a call)")
    nodes = wf.get("nodes") or {}
    glob = wf.get("global_nodes") or {}
    allk = set(nodes) | set(glob)
    if wf.get("initial_node") not in nodes:
        E(f"initial_node {wf.get('initial_node')!r} is not a node")
    api_paths = set()
    if openapi:
        api_paths = {p.strip("/") for p in openapi.get("paths", {})}
    reach_end = {k for k, n in nodes.items() if n.get("node_type") == "end_call"}
    if not reach_end:
        W("no end_call node: the call ends only by an end_call tool or a closing phrase")
    for key, n in list(nodes.items()) + [(f"global:{k}", g) for k, g in glob.items()]:
        t = n.get("node_type", "conversation" if key.startswith("global:") else None)
        where = f"node {key}"
        if not key.startswith("global:") and n.get("name") not in (None, key):
            W(f"{where}: name {n.get('name')!r} differs from the key")
        if t not in NODE_TYPES and not key.startswith("global:"):
            E(f"{where}: node_type {t!r} is not one of {sorted(NODE_TYPES)}")
        if n.get("tools") and t != "conversation":
            E(f"{where}: tools on a {t} node are dropped by the platform (only conversation nodes keep tools)")
        if n.get("pre_actions") and t == "conversation":
            E(f"{where}: pre_actions on a conversation node are dropped (use an api_request or code node in front)")
        trs = n.get("transitions") or []
        for tr in trs:
            tgt = tr.get("target_node")
            if tgt != "__previous__" and tgt not in allk:
                E(f"{where}: transition to unknown node {tgt!r}")
            cond = tr.get("condition") or {}
            if cond.get("logic") == "and":
                E(f"{where}: a top-level condition group with logic 'and' (nest it inside an 'or' group)")
            for c in conditions(cond):
                op = c.get("operator")
                if op in ("equals", "not_equals") and str(c.get("operand")).lower() in ("true", "false"):
                    var, val = c.get("variable"), str(c.get("operand"))
                    other = val.capitalize() if val.islower() else val.lower()
                    leaves = conditions(cond)
                    if not any(x.get("variable") == var and str(x.get("operand")) == other for x in leaves):
                        E(f"{where}: {var} equals {val!r} without {other!r} (booleans arrive as 'true' or 'True')")
                if op in DET_OPS and not c.get("variable"):
                    E(f"{where}: operator {op} without a variable")
        if n.get("passthrough"):
            if not trs or (trs[-1].get("condition") or {}).get("operator") != "always":
                E(f"{where}: a passthrough node must end with an 'always' transition (it deadlocks otherwise)")
            if not n.get("passthrough_default_transition"):
                W(f"{where}: passthrough node without passthrough_default_transition")
        if t == "end_call":
            if trs:
                E(f"{where}: an end_call node has transitions")
            term = (n.get("terminal") or {}).get("function", {})
            if term.get("handler") != "__function__:end_call":
                E(f"{where}: terminal handler must be __function__:end_call")
            if (n.get("on_enter") or {}).get("type") not in (None, "silent"):
                W(f"{where}: an end_call node speaks on_enter; the farewell belongs in terminal.spoken_message")
        if n.get("max_node_turns") and not n.get("max_turn_transition"):
            W(f"{where}: max_node_turns without max_turn_transition does nothing")
        maps = list(n.get("response_mapping") or [])
        for pa in n.get("pre_actions") or []:
            if pa.get("response_mapping"):
                E(f"{where}: response_mapping inside a pre_action is ignored (put it on the node)")
            maps += []
        for tl in n.get("tools") or []:
            maps += tl.get("response_mapping") or []
        for m in maps:
            if not str(m.get("path", "")).startswith("data."):
                E(f"{where}: response_mapping path {m.get('path')!r} must start with 'data.'")
        for fn in (n.get("pre_actions") or []) + (n.get("tools") or []):
            f = fn.get("function", {})
            params = f.get("parameters", {}).get("properties", {})
            if f.get("handler") == "__function__:code_exec":
                code = str(params.get("code", {}).get("default", ""))
                if "{{" in code or "}}" in code:
                    E(f"{where}: code of {f.get('name')} contains '{{{{' or '}}}}' (read values from vars)")
                try:
                    compile(code, f"{key}.{f.get('name')}", "exec")
                except SyntaxError as e:
                    E(f"{where}: code of {f.get('name')} does not compile: {e}")
            if f.get("handler") == "__function__:api_call":
                for p in ("url", "method"):
                    if "default" not in params.get(p, {}):
                        E(f"{where}: {f.get('name')}.{p} has no default (const does not bake)")
                body = params.get("body", {})
                if "default" in body and not body.get("properties"):
                    W(f"{where}: {f.get('name')} body is one default object; declare each field under body.properties")
                if api_paths:
                    url = str(params.get("url", {}).get("default", ""))
                    if not any(url.rstrip("/").endswith("/" + p) for p in api_paths):
                        W(f"{where}: {f.get('name')} url {url!r} is not a path of the tool API")
                for hk in ("pre_process_code", "post_process_code"):
                    if fn.get(hk):
                        try:
                            compile(fn[hk], f"{key}.{f.get('name')}.{hk}", "exec")
                        except SyntaxError as e:
                            E(f"{where}: {hk} of {f.get('name')} does not compile: {e}")
        if t == "conversation" and n.get("tools") and not re.search(r"call|CALL", str(n.get("task_message", ""))):
            W(f"{where}: has tools but the task_message does not say when to call them")
        for ex in n.get("extraction_schema") or []:
            if "min_confidence" not in ex:
                W(f"{where}: extraction {ex.get('name')} has no min_confidence (the default 0.95 drops most values)")
            if "extraction_prompt" in ex and "{{extractor.speech}}" not in ex["extraction_prompt"]:
                E(f"{where}: extraction_prompt of {ex.get('name')} has no {{{{extractor.speech}}}}: the extractor sees nothing")
    # Every node must be reachable from the initial node, and every node must reach an end_call node.
    edges = {k: {tr.get("target_node") for tr in (n.get("transitions") or [])} | ({n["passthrough_default_transition"]} if n.get("passthrough_default_transition") else set()) | ({n["max_turn_transition"]} if n.get("max_turn_transition") else set()) for k, n in nodes.items()}
    seen, todo = set(), [wf.get("initial_node")]
    globals_targets = {tr.get("target_node") for g in glob.values() for tr in (g.get("transitions") or [])}
    while todo:
        k = todo.pop()
        if k in seen or k not in nodes:
            continue
        seen.add(k)
        todo += list(edges.get(k, ()))
    todo = [t for t in globals_targets if t in nodes]
    while todo:
        k = todo.pop()
        if k in seen or k not in nodes:
            continue
        seen.add(k)
        todo += list(edges.get(k, ()))
    for k in nodes:
        if k not in seen:
            W(f"node {k}: not reachable from the initial node")
    return errors, warnings


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    wf = json.load(open(args[0]))
    wf = wf.get("workflow", wf)
    oa = json.load(open(args[args.index("--openapi") + 1])) if "--openapi" in args else None
    errs, warns = check(wf, oa)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    print(f"{len(errs)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errs else 0)
