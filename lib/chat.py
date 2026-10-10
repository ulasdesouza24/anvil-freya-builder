"""Talk to a published workflow turn by turn, with no simulation queue (docs/api.md, POST /api/v2/chat/message).

    python lib/chat.py <workflow_id> --case PUB-01 "Yes, that's me" "14 March 1988" "4471" ...
    python lib/chat.py <workflow_id> --vars '{"customer_id": "c_x", "first_name": "Ann", ...}' "Hello?" ...

--case starts a practice session on the bank mock, so the tools work on a real practice customer. Each user message
is one turn. It prints what the agent said, and at the end the tool calls of the call (lib/analyze_call.py).
Seen in tests: a code step as the first step can be skipped by the chat route. A simulation is the real test.
"""
import json, os, sys, time, urllib.request

KIT = os.environ.get("KIT", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kit"))
sys.path.insert(0, KIT)
sys.path.insert(0, os.path.join(KIT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def practice_vars(case_id):
    from score import http

    r = http("/v1/practice/sessions", {"case": case_id})
    if not r.get("variables"):
        raise SystemExit(f"no practice session for {case_id}: {r}")
    return r["variables"]


def main():
    import freya
    from analyze_call import story

    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    wid, msgs, variables = a[0], [], {}
    # lib/test.py starts the first test of a slot only after a chat check of the workflow.
    mark = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", ".chat-checks")
    os.makedirs(mark, exist_ok=True)
    open(os.path.join(mark, wid), "w").write(str(time.time()))
    i = 1
    while i < len(a):
        if a[i] == "--case":
            variables = practice_vars(a[i + 1])
            i += 2
        elif a[i] == "--vars":
            variables = json.loads(a[i + 1])
            i += 2
        else:
            msgs.append(a[i])
            i += 1
    call_id = None
    for m in msgs or ["Hello?"]:
        body = {"workflowId": wid, "message": m, "customerVariables": variables}
        if call_id:
            body["callId"] = call_id
        t = time.time()
        try:
            r = freya.api("POST", "/api/v2/chat/message", body)
        except Exception as e:
            print(f"USER  {m}\n  !! {e}")
            break
        call_id = r.get("callId") or call_id
        print(f"USER  {m}\nAGENT {r.get('response')}   ({time.time() - t:.1f}s)")
    if call_id:
        try:
            freya.api("POST", "/api/v2/chat/end", {"callId": call_id})
        except Exception:
            pass
        try:
            print("\n--- call events ---\n" + story(freya.get_call(call_id)))
        except Exception as e:
            print(f"(no call events: {e})")


if __name__ == "__main__":
    main()
