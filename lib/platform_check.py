"""Are the Freya chat service and the bank's tool API up? Exit code 0 when both answer, 1 when one does not.

    python lib/platform_check.py <workflow_id> [<tool API file>]

The chat check is one chat turn on the workflow. The tool API check is one call of the first path of the tool API
file with an unknown customer id: an answer with HTTP 200 (also with ok false) means that the service is up.

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
    up = True
    if len(sys.argv) > 2:
        import urllib.request

        oa = json.load(open(sys.argv[2]))
        url = (oa.get("servers") or [{}])[0].get("url", "").rstrip("/") + "/" + next(iter(oa.get("paths", {})), "").strip("/")
        try:
            req = urllib.request.Request(url, data=b'{"customer_id": "c_platform_check"}', headers={"content-type": "application/json", "user-agent": "Mozilla/5.0 (anvil-builder)"}, method="POST")
            code = urllib.request.urlopen(req, timeout=20).status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:
            code = str(e)[:80]
        print(("TOOL API UP" if code == 200 else "TOOL API DOWN") + f": {url} -> {code}")
        up = code == 200
    try:
        r = freya.api("POST", "/api/v2/chat/message", {"workflowId": sys.argv[1], "message": "Hello?", "customerVariables": {"customer_id": "c_platform_check", "first_name": "Test", "last_name": "Check", "title": "Mr", "now": "2026-10-14T11:00"}})
        if r.get("callId"):
            try:
                freya.api("POST", "/api/v2/chat/end", {"callId": r["callId"]})
            except Exception:
                pass
        print("CHAT UP:", (r.get("response") or "")[:80])
        sys.exit(0 if up else 1)
    except Exception as e:
        print("CHAT DOWN:", str(e)[:200])
        sys.exit(1)
