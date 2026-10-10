"""The trace screen: a local web page that shows the builder runs as they happen.

    python3 lib/dashboard.py [--port 8765]      # then open http://localhost:8765

It reads only local files (traces/, work/<slot>/, results/rehearsal-*/) and the simulation list of the workspace.
It changes nothing. Source the kit's env.sh first, or the simulation list stays empty.
"""
import argparse, glob, json, os, pathlib, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
LINE = re.compile(r"^(\S+) \+\s*(\d+)s (\S+)\s+(.*)$")
_queue = {"at": 0, "items": [], "error": ""}


def queue():
    """The last simulations of the workspace, read at most every 20 s."""
    if time.time() - _queue["at"] > 20:
        _queue["at"] = time.time()
        try:
            import sim_queue

            _queue["items"] = [{"name": s.get("name"), "status": s.get("status"), "agent": s.get("agentId"),
                                "created": s.get("createdAt")} for s in sim_queue.recent(8)]
            _queue["error"] = ""
        except Exception as e:
            _queue["error"] = str(e)[:200]
    return _queue


def parse_trace(path):
    lines = pathlib.Path(path).read_text(errors="replace").splitlines()
    ev = []
    for l in lines:
        m = LINE.match(l)
        if m:
            ev.append({"time": m.group(1)[11:19], "t": int(m.group(2)), "kind": m.group(3), "text": m.group(4)})
    start = next((e for e in ev if e["kind"] == "start"), None)
    budget = 28
    if start:
        m = re.search(r"budget=([\d.]+)min", start["text"])
        budget = float(m.group(1)) if m else budget
    slot = pathlib.Path(path).stem.split("-", 2)[-1]
    ids = {}
    for e in ev:
        for k in ("workflow_id", "agent_id"):
            m = re.search(k + r'"?[=:]\s*"?([0-9a-f-]{36})', e["text"])
            if m:
                ids[k] = m.group(1)
    # A trace with no 'end' line and no new line for 10 minutes belongs to a killed run.
    cut = not any(e["kind"] == "end" for e in ev) and time.time() - pathlib.Path(path).stat().st_mtime > 600
    ended = cut or any(e["kind"] == "end" for e in ev)
    elapsed = ev[-1]["t"] if ev else 0
    if not ended and lines:
        # A running build: the time since its first trace line.
        try:
            elapsed = int(time.time() - time.mktime(time.strptime(lines[0][:19], "%Y-%m-%dT%H:%M:%S")))
        except Exception:
            pass
    return {
        "file": pathlib.Path(path).name, "slot": slot, "ended": ended, "elapsed": elapsed, "budget": budget * 60,
        "calls": sum(1 for e in ev if e["kind"] == "model"), "ids": ids,
        "tests": [e for e in ev if e["kind"] == "test"], "events": ev[-60:],
        "end": next((e["text"] for e in ev if e["kind"] == "end"), "no end line: the run was killed" if cut else ""),
        "stopped": cut or any(e["kind"] in ("stop", "timeout", "error") for e in ev),
    }


def slot_state(slot):
    d = ROOT / "work" / slot
    hist = json.loads((d / "history.json").read_text()) if (d / "history.json").exists() else []
    runs = []
    for f in sorted(d.glob("run*.json"), key=lambda p: p.stat().st_mtime):
        try:
            r = json.loads(f.read_text())
        except Exception:
            continue
        rows = r.get("rows") or []
        runs.append({"file": f.name, "passed": r.get("passed"), "total": r.get("total"), "seconds": r.get("seconds"),
                     "customers": [{"id": x.get("id"), "pass": x.get("pass"), "why": (x.get("failed") or [""])[0][:300]} for x in rows]})
    logs = sorted(d.glob("run*.log"), key=lambda p: p.stat().st_mtime)
    live = logs[-1].read_text(errors="replace").splitlines()[-6:] if logs else []
    return {"versions": [{"version": h["version"], "plain": [(x["passed"], x["total"]) for x in h["plain"]],
                          "style": [(x["style"], x["passed"], x["total"]) for x in h["style"]]} for h in hist],
            "runs": runs, "live": live, "files": sorted(p.name for p in d.glob("*") if p.is_file())}


def rehearsal():
    dirs = sorted(glob.glob(str(ROOT / "results" / "rehearsal-*")))
    if not dirs:
        return None
    d = pathlib.Path(dirs[-1])
    prog = (d / "progress.log").read_text().splitlines() if (d / "progress.log").exists() else []
    summ = (d / "summary.md").read_text() if (d / "summary.md").exists() else ""
    return {"name": d.name, "progress": prog[-40:], "summary": summ}


def state(selected=None):
    traces = sorted(glob.glob(str(ROOT / "traces" / "*.log")), key=os.path.getmtime, reverse=True)
    traces = [t for t in traces if not t.endswith(".console.log")][:12]
    builds = [parse_trace(t) for t in traces]
    cur = next((b for b in builds if b["file"] == selected), builds[0] if builds else None)
    return {"now": time.strftime("%H:%M:%S"), "builds": [{k: b[k] for k in ("file", "slot", "ended", "elapsed", "budget", "calls", "stopped", "end")} | {"tests": len(b["tests"])} for b in builds],
            "current": cur, "slot": slot_state(cur["slot"]) if cur else None, "rehearsal": rehearsal(), "queue": queue()}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Builder Trace</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#667085;--line:#e4e7ec;--ok:#0f9d58;--bad:#d93025;--warn:#c77700;--acc:#3b5bdb;--code:#f1f3f5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1115;--card:#171a21;--ink:#e6e8ec;--mute:#98a2b3;--line:#272b35;--ok:#34c47c;--bad:#ff6b5f;--warn:#f0a73a;--acc:#7c9cff;--code:#1e222b}}
:root[data-theme="dark"]{--bg:#0f1115;--card:#171a21;--ink:#e6e8ec;--mute:#98a2b3;--line:#272b35;--ok:#34c47c;--bad:#ff6b5f;--warn:#f0a73a;--acc:#7c9cff;--code:#1e222b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:2}
header h1{font-size:16px;margin:0}.mute{color:var(--mute)}.grow{flex:1}
main{display:grid;grid-template-columns:280px 1fr 360px;gap:16px;padding:16px 20px}
@media (max-width:1100px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:16px;min-width:0}
.card h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin:0 0 10px}
.build{padding:8px 10px;border-radius:8px;cursor:pointer;border:1px solid transparent;margin-bottom:4px}
.build:hover{background:var(--code)}.build.sel{border-color:var(--acc);background:var(--code)}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600}
.run{background:color-mix(in srgb,var(--acc) 18%,transparent);color:var(--acc)}.done{background:color-mix(in srgb,var(--ok) 18%,transparent);color:var(--ok)}
.stop{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad)}
.bar{height:8px;background:var(--code);border-radius:99px;overflow:hidden;margin:6px 0}.bar>div{height:100%;background:var(--acc)}
.bar.late>div{background:var(--warn)}
.big{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}
.ev{display:grid;grid-template-columns:62px 70px 1fr;gap:8px;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px}
.ev .k{font-weight:600}.k-model{color:var(--mute)}.k-test{color:var(--ok)}.k-created{color:var(--acc)}.k-error,.k-stop,.k-timeout{color:var(--bad)}.k-best,.k-restore,.k-export{color:var(--warn)}
.ev .x{overflow-wrap:anywhere}
.cust{display:flex;gap:8px;align-items:flex-start;padding:4px 0;border-bottom:1px solid var(--line);font-size:13px}
.dot{width:10px;height:10px;border-radius:50%;margin-top:5px;flex:none}.dot.ok{background:var(--ok)}.dot.bad{background:var(--bad)}
pre{background:var(--code);padding:10px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;margin:0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left}
.stats{display:flex;gap:18px;flex-wrap:wrap}.stats div{min-width:90px}
</style></head><body>
<header><h1>Builder trace</h1><span class="mute" id="now"></span><span class="grow"></span><span class="mute">refreshes every 4 s</span></header>
<main>
 <div><div class="card"><h2>Builds</h2><div id="builds"></div></div>
      <div class="card"><h2>Freya simulations</h2><div id="queue"></div></div></div>
 <div><div class="card" id="head"></div><div class="card"><h2>Events (newest first)</h2><div id="events"></div></div></div>
 <div><div class="card"><h2>Running test</h2><pre id="live">-</pre></div>
      <div class="card"><h2>Last test, by customer</h2><div id="custs"></div></div>
      <div class="card"><h2>Tested versions</h2><div id="versions"></div></div>
      <div class="card"><h2>Rehearsal</h2><div id="reh"></div></div></div>
</main>
<script>
let sel=null;const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const mmss=s=>`${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;
function status(b){return b.ended?(b.stopped?'<span class="pill stop">stopped</span>':'<span class="pill done">done</span>'):'<span class="pill run">running</span>'}
async function tick(){
 let d;try{d=await (await fetch("/api/state"+(sel?"?build="+encodeURIComponent(sel):""))).json()}catch(e){$("now").textContent="no connection";return}
 $("now").textContent=d.now;
 $("builds").innerHTML=d.builds.map(b=>`<div class="build ${d.current&&b.file===d.current.file?"sel":""}" data-f="${esc(b.file)}"><div>${status(b)} <b>${esc(b.slot)}</b></div><div class="mute">${esc(b.file.slice(0,15))} · ${mmss(b.elapsed)} · ${b.calls} calls · ${b.tests} test lines</div></div>`).join("")||'<span class="mute">no build yet</span>';
 document.querySelectorAll(".build").forEach(e=>e.onclick=()=>{sel=e.dataset.f;tick()});
 const q=d.queue;$("queue").innerHTML=q.error?`<span class="mute">${esc(q.error)}</span>`:q.items.map(s=>`<div class="cust"><span class="dot ${s.status==="completed"?"ok":s.status==="running"||s.status==="queued"?"":"bad"}" style="${s.status==="running"||s.status==="queued"?"background:var(--acc)":""}"></span><div><b>${esc(s.status)}</b> ${esc(s.name)}<div class="mute">started ${esc((s.created||"").slice(11,19))} UTC · agent ${esc((s.agent||"").slice(0,8))}</div></div></div>`).join("")||'<span class="mute">none</span>';
 const c=d.current;if(!c){$("head").innerHTML="<h2>No build</h2>";return}
 const pct=Math.min(100,100*c.elapsed/c.budget),left=Math.max(0,c.budget-c.elapsed);
 $("head").innerHTML=`<h2>${esc(c.slot)} ${status(c)}</h2><div class="stats"><div><div class="mute">time</div><div class="big">${mmss(c.elapsed)}</div></div><div><div class="mute">left of ${c.budget/60} min</div><div class="big">${c.ended?"-":mmss(Math.round(left))}</div></div><div><div class="mute">model calls</div><div class="big">${c.calls}</div></div><div><div class="mute">workflow</div><div>${esc((c.ids.workflow_id||"-").slice(0,8))}</div><div class="mute">agent ${esc((c.ids.agent_id||"-").slice(0,8))}</div></div></div><div class="bar ${pct>80?"late":""}"><div style="width:${pct}%"></div></div>${c.end?`<div class="mute">end: ${esc(c.end)}</div>`:""}`;
 $("events").innerHTML=c.events.slice().reverse().map(e=>`<div class="ev"><span class="mute">${esc(e.time)}</span><span class="k k-${esc(e.kind)}">${esc(e.kind)}</span><span class="x">${esc(e.text)}</span></div>`).join("");
 const s=d.slot||{};$("live").textContent=(s.live||[]).join("\n")||"-";
 const r=(s.runs||[]).slice(-1)[0];
 $("custs").innerHTML=r?`<div class="mute">${esc(r.file)}: <b>${r.passed}/${r.total}</b> in ${r.seconds} s</div>`+r.customers.map(x=>`<div class="cust"><span class="dot ${x.pass?"ok":"bad"}"></span><div><b>${esc(x.id)}</b>${x.pass?"":`<div class="mute">${esc(x.why)}</div>`}</div></div>`).join(""):'<span class="mute">no test yet</span>';
 $("versions").innerHTML=(s.versions||[]).length?`<table><tr><th>v</th><th>plain</th><th>style</th></tr>${s.versions.map(v=>`<tr><td>${v.version}</td><td>${v.plain.map(p=>p[0]+"/"+p[1]).join(", ")||"-"}</td><td>${v.style.map(p=>p[0]+" "+p[1]+"/"+p[2]).join(", ")||"-"}</td></tr>`).join("")}</table>`:'<span class="mute">none</span>';
 const h=d.rehearsal;$("reh").innerHTML=h?`<div class="mute">${esc(h.name)}</div><pre>${esc((h.summary||h.progress.slice(-15).join("\n"))||"-")}</pre>`:'<span class="mute">none</span>';
}
tick();setInterval(tick,4000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/api/state"):
            from urllib.parse import parse_qs, urlparse

            sel = (parse_qs(urlparse(self.path).query).get("build") or [None])[0]
            body = json.dumps(state(sel), default=str).encode()
            ctype = "application/json"
        else:
            body, ctype = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"trace screen: http://localhost:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
