"""The simulation queue of the workspace. One simulation runs at a time, and a simulation cannot be stopped: a test
that is stopped on this side keeps running on Freya until it ends, and the next test waits for it.

    python lib/sim_queue.py            # prints the running simulations
    python lib/sim_queue.py --wait     # waits until no simulation runs
"""
import os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get("KIT", str(ROOT / "kit")))


def recent(limit=10):
    import freya

    r = freya.api("GET", f"/api/v2/simulations?limit={limit}")
    items = r.get("simulations") or r.get("items") or [] if isinstance(r, dict) else r
    return items if isinstance(items, list) else []


def running():
    return [s for s in recent() if s.get("status") not in ("completed", "failed", "paused")]


def wait_empty(say=print, every=20, limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            busy = running()
        except Exception as e:
            say(f"cannot read the simulation list: {str(e)[:120]}")
            return False
        if not busy:
            return True
        say("waiting for " + ", ".join(f"{s.get('name')} ({s.get('status')}, started {s.get('createdAt', '')[11:19]} UTC)" for s in busy))
        time.sleep(every)
    return False


if __name__ == "__main__":
    if "--wait" in sys.argv:
        sys.exit(0 if wait_empty() else 1)
    busy = running()
    print("\n".join(f"{s['id']} {s.get('status')} {s.get('name')} agent {s.get('agentId')}" for s in busy) or "no simulation runs")
