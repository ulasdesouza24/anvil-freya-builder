"""Is the Freya chat service up? One chat turn on a workflow. Exit code 0 when it answers, 1 when it does not.

    python lib/platform_check.py <workflow_id>

Use it when a test gives no tool call for every customer, or when chat gives 503. Wait at least 2 minutes between
two checks: the rules forbid load on the platform.
"""
import json, os, sys

KIT = os.environ.get("KIT", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kit"))
sys.path.insert(0, KIT)

if __name__ == "__main__":
    import freya

    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        r = freya.api("POST", "/api/v2/chat/message", {"workflowId": sys.argv[1], "message": "Hello?", "customerVariables": {"customer_id": "c_platform_check", "first_name": "Test", "last_name": "Check", "title": "Mr", "now": "2026-10-14T11:00"}})
        if r.get("callId"):
            try:
                freya.api("POST", "/api/v2/chat/end", {"callId": r["callId"]})
            except Exception:
                pass
        print("UP:", (r.get("response") or "")[:80])
        sys.exit(0)
    except Exception as e:
        print("DOWN:", str(e)[:200])
        sys.exit(1)
