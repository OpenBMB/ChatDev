#!/usr/bin/env python3
"""SGAR adapter for Zotero Translation Server metadata extraction."""
from __future__ import annotations
import argparse, json, os
import httpx

# The launcher supplies a project-scoped proxy and explicit local-service
# NO_PROXY entries. Honor those routes, including when the service is remote.

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("identifier"); p.add_argument("--base-url",default=os.environ.get("ZOTERO_TRANSLATION_SERVER_URL","http://translation-server:1969")); p.add_argument("--timeout-ms",type=int,default=20000); a=p.parse_args()
    try:
        with httpx.Client(timeout=a.timeout_ms/1000,trust_env=True) as c:
            r=c.post(a.base_url.rstrip("/")+"/search",content=a.identifier.encode(),headers={"Content-Type":"text/plain"})
        value=r.json();
        if r.status_code>=400: print(json.dumps({"status":"error","tool":"zotero_translation","http_status":r.status_code,"response":value},ensure_ascii=False)); return 1
        print(json.dumps({"status":"success","tool":"zotero_translation","identifier":a.identifier,"items":value if isinstance(value,list) else value.get("items",value)},ensure_ascii=False)); return 0
    except Exception as exc: print(json.dumps({"status":"error","tool":"zotero_translation","message":str(exc)})); return 1
if __name__ == "__main__": raise SystemExit(main())
