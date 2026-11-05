"""Shared helper for rest_api tool wrappers: real HTTP call + uniform JSON."""
import sys, json, os

def emit(o):
    payload = json.dumps(o, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(payload)
        sys.stdout.flush()
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_payload = payload.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(safe_payload)
        sys.stdout.flush()
def get(url, tool, params=None, headers=None, timeout=25):
    # Keep the wrapper importable for manifest inspection and static validation.
    # ``requests`` is a declared runtime dependency and is only needed when the
    # tool actually performs an HTTP operation.
    try:
        import requests
    except ImportError as e:
        emit({"status":"error","tool":tool,"message":f"missing runtime dependency: {e.name}"})
        sys.exit(1)
    try:
        r = requests.get(url, params=params or {}, headers=headers or {"User-Agent":"S-GAR/1.0"}, timeout=timeout)
        ct = r.headers.get("content-type","")
        body = r.json() if "json" in ct else r.text
        if not 200 <= r.status_code < 400:
            emit({"status":"error","tool":tool,"url":r.url,"http_status":r.status_code,"result":body})
            sys.exit(1)
        emit({"status":"success","tool":tool,"url":r.url,"http_status":r.status_code,"result":body})
    except requests.RequestException as e:
        emit({"status":"error","tool":tool,"message":f"{type(e).__name__}: {e}"}); sys.exit(1)
def arg(i, default=None):
    return sys.argv[i] if len(sys.argv)>i else default

a = arg
