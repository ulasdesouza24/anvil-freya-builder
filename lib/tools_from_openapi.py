"""Freya tool objects from the bank's OpenAPI file.

    python lib/tools_from_openapi.py tools/openapi.json [--out out/tools.json] [--guide guide.json]

For each POST path it writes one `api_call` tool, as docs/tools-and-code.md says:
- url and method are baked with `default`. A field named like a call variable (customer_id) is baked from it.
- every other body field is a leaf under body.properties with its type, description and enum. Its default is a
  placeholder that no variable has (`{{<tool>__<field>}}`), so the model fills it.
- writes get maxRetries 0 (a retried write can record a thing two times), reads get 2.
- a post-hook removes the headers and adds `what_to_do_next` to the result: the agent model often says nothing
  after a bare result, or reads a failure as a success. The text for each tool comes from --guide (written by the
  builder from the brief), with a generic text for a failure.

The output is a JSON object {tool name: tool object}. A builder copies the tools into the nodes that need them.
"""
import json, re, sys

CALL_VARIABLES = {"customer_id"}
# verify_* counts wrong answers, so it is not a plain read: it gets no retry.
READ_HINT = re.compile(r"^(get|list|find|lookup|read)_")

HOOK = r'''
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
        "post_process_code": HOOK.replace("__GUIDE__", repr({"failed": g.get("failed", ""), "ok": g.get("ok", ""), "when": [tuple(x) for x in g.get("when", [])]})).strip() + "\n",
    }
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
