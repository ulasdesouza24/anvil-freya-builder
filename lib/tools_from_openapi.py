"""Freya tool objects from the bank's OpenAPI file.

    python lib/tools_from_openapi.py tools/openapi.json [--out out/tools.json] [--guide guide.json]

For each POST path it writes one `api_call` tool, as docs/tools-and-code.md says:
- url and method are baked with `default`. A field named like a call variable (customer_id) is baked from it.
- every other body field is a leaf under body.properties with its type, description and enum. Its default is a
  placeholder that no variable has (`{{<tool>__<field>}}`), so the model fills it.
- writes get maxRetries 0 (a retried write can record a thing two times), reads get 2.
- a pre-hook of a write tool writes its request as variables (`<tool>_request__<field>`) before the call. A close
  guard reads them: the model can call a write tool and the close tool in the same turn, and then the close guard
  runs before the result of the write exists (seen: a transfer and a close together, closed as a refusal).
- a post-hook removes the headers and adds `what_to_do_next` to the result: the agent model often says nothing
  after a bare result, or reads a failure as a success. The text for each tool comes from --guide (written by the
  builder from the brief), with a generic text for a failure.

The output is a JSON object {tool name: tool object}. A builder copies the tools into the nodes that need them.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spoken

CALL_VARIABLES = {"customer_id"}
# verify_* counts wrong answers, so it is not a plain read: it gets no retry.
READ_HINT = re.compile(r"^(get|list|find|lookup|read)_")

PRE_HOOK = r'''
try:
    b = config.get("body")
    if isinstance(b, dict):
        plan = __PLAN__
        order = __ORDER__
        now = str(vars.get("now") or "")
        year = int(now[:4]) if now[:4].isdigit() else None
        for f, kind in plan.items():
            v = b.get(f)
            if v is None or v == "":
                continue
            if kind == "number" and isinstance(v, str):
                n = words_to_number(v)
                if n is not None:
                    b[f] = int(n) if n == int(n) else n
            elif kind == "date" and isinstance(v, str):
                d = spoken_date(v, order, year)
                if d:
                    b[f] = d
            elif kind == "digits":
                d = digits(str(v))
                if d:
                    b[f] = d
            elif kind == "time" and isinstance(v, str):
                m = re.search(r"([0-9]{1,2})[:.h ]?([0-9]{2})?", v)
                if m:
                    b[f] = "%02d:%02d" % (int(m.group(1)), int(m.group(2) or 0))
            elif kind == "date_or_digits" and isinstance(v, str):
                d = spoken_date(v, order, None)
                if d:
                    b[f] = d
                else:
                    g = digits(v)
                    if g:
                        b[f] = g
except Exception:
    pass
'''


# For a write tool: its request (after the normalization above) as variables, at the time of the call.
REQUEST_HOOK = r'''
try:
    b = config.get("body")
    if isinstance(b, dict):
        vars["__TOOL___requested"] = "true"
        for k, v in b.items():
            vars["__TOOL___request__" + str(k)] = str(v)
except Exception:
    pass
'''


def normalize_plan(props):
    """What a pre-hook does with each body field, from the field's type, format and description."""
    plan = {}
    for field, spec in props.items():
        desc = (spec.get("description") or "").lower()
        t, fmt = spec.get("type"), spec.get("format")
        has_date = fmt == "date" or "yyyy-mm-dd" in desc
        has_digits = "digit" in desc
        if spec.get("enum"):
            continue
        if t in ("number", "integer"):
            plan[field] = "number"
        elif has_date and has_digits:
            plan[field] = "date_or_digits"
        elif has_date:
            plan[field] = "date"
        elif has_digits:
            plan[field] = "digits"
        elif "hh:mm" in desc:
            plan[field] = "time"
    return plan


HOOK = r'''
import json
try:
    if isinstance(result, dict):
        result.pop("header", None)
        d = result.get("data")
        code = result.get("status_code")
        guide = __GUIDE__
        if not isinstance(d, dict):
            result["data"] = d = {"ok": False, "error": "the service gave no answer"}
        failed = d.get("ok") is False or (isinstance(code, int) and code >= 500) or result.get("status") not in (None, "success")
        if failed:
            d["ok"] = False
            d["what_to_do_next"] = guide.get("failed") or ("This action was NOT carried out (" + str(d.get("error") or "service error") + "). Do not say that it worked. Follow the brief for a failed action.")
        else:
            lines = []
            for key, text in guide.get("when", []):
                k, _, want = key.partition("=")
                v = d.get(k)
                if (want == "" and v not in (None, "", [], {})) or (want != "" and str(v).lower() == want.lower()):
                    lines.append(text)
            d["what_to_do_next"] = " ".join(lines) or guide.get("ok") or "The action worked. Tell the customer the result in one short sentence, then continue."
        # Code steps cannot read the result keys of the engine, and a response_mapping of a list sets nothing (seen on
        # the platform). The hook writes each result field as a variable: <tool>_result__<field>, lists as JSON text.
        try:
            for k, v in d.items():
                if k == "what_to_do_next":
                    continue
                vars["__TOOL___result__" + str(k)] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
                if isinstance(v, list):
                    vars["__TOOL___result__" + str(k) + "_count"] = str(len(v))
        except Exception:
            pass
except Exception:
    pass
'''


def tool_for(path, op, server, guide):
    name = path.strip("/").replace("/", "_")
    schema = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    props, required = schema.get("properties") or {}, schema.get("required") or []
    body = {}
    for field, spec in props.items():
        leaf = {"type": spec.get("type", "string")}
        desc = spec.get("description") or ""
        if spec.get("enum"):
            leaf["enum"] = spec["enum"]
            desc = (desc + " " if desc else "") + "One of: " + ", ".join(map(str, spec["enum"])) + "."
        if spec.get("format") == "date":
            desc = (desc + " " if desc else "") + "A date as YYYY-MM-DD."
        if desc:
            leaf["description"] = desc
        leaf["default"] = "{{" + field + "}}" if field in CALL_VARIABLES else "{{" + f"{name}__{field}" + "}}"
        body[field] = leaf
    write = not READ_HINT.match(name)
    g = guide.get(name, {})
    tool = {
        "type": "function",
        "config": {"timeoutMs": 15000, "maxRetries": 0 if write else 2},
        "function": {
            "name": name,
            "handler": "__function__:api_call",
            "description": g.get("description") or (op.get("summary") or name),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "default": server.rstrip("/") + "/" + path.strip("/")},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "properties": body, "required": [f for f in required if f not in CALL_VARIABLES]},
                },
            },
        },
        "post_process_code": HOOK.replace("__TOOL__", name).replace("__GUIDE__", repr({"failed": g.get("failed", ""), "ok": g.get("ok", ""), "when": [tuple(x) for x in g.get("when", [])]})).strip() + "\n",
    }
    # Spoken values (amounts and dates in words, digits as words) become the form of the API before the call.
    plan = {k: v for k, v in {**normalize_plan(props), **g.get("normalize", {})}.items() if v and v != "none"}
    pre = ""
    if plan:
        pre = spoken.SOURCE.strip() + "\n" + PRE_HOOK.replace("__PLAN__", repr(plan)).replace("__ORDER__", repr(guide.get("_date_order", "DMY"))).strip() + "\n"
    if write:
        pre += REQUEST_HOOK.replace("__TOOL__", name).strip() + "\n"
    if pre:
        tool["pre_process_code"] = pre
    for code in (tool.get("pre_process_code", ""), tool["post_process_code"]):
        if code:
            if "{{" in code or "}}" in code:
                raise ValueError(f"the hook of {name} contains '{{{{' or '}}}}'")
            compile(code, name, "exec")
    if g.get("response_mapping"):
        tool["response_mapping"] = g["response_mapping"]
    return name, tool


def tools(openapi, guide=None):
    guide = guide or {}
    server = (openapi.get("servers") or [{}])[0].get("url", "")
    out = {}
    for path, item in (openapi.get("paths") or {}).items():
        op = item.get("post")
        if op:
            name, tool = tool_for(path, op, server, guide)
            out[name] = tool
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    oa = json.load(open(a[0]))
    g = json.load(open(a[a.index("--guide") + 1])) if "--guide" in a else {}
    res = tools(oa, g)
    text = json.dumps(res, indent=1)
    if "--out" in a:
        open(a[a.index("--out") + 1], "w").write(text)
        print(f"{len(res)} tools: {', '.join(res)}")
    else:
        print(text)
