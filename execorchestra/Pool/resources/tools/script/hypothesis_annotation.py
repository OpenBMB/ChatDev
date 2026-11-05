#!/usr/bin/env python3
"""SGAR adapter for Hypothesis annotation read/write API."""
from __future__ import annotations
import argparse, json, os
import httpx

# The launcher supplies a project-scoped proxy and explicit local-service
# NO_PROXY entries. Honor those routes, including when the service is remote.

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("uri"); p.add_argument("--quote"); p.add_argument("--prefix",default=""); p.add_argument("--suffix",default=""); p.add_argument("--text",default=""); p.add_argument("--base-url",default=os.environ.get("HYPOTHESIS_API_URL","http://hypothesis:5000/api")); p.add_argument("--token-env",default="HYPOTHESIS_API_TOKEN"); a=p.parse_args(); headers={}; token=os.environ.get(a.token_env,"").strip()
    if token: headers["Authorization"]="Bearer "+token
    payload={"uri":a.uri,"text":a.text,"target":[{"source":a.uri,"selector":[{"type":"TextQuoteSelector","exact":a.quote or "","prefix":a.prefix,"suffix":a.suffix}]}]}
    try:
        with httpx.Client(timeout=20,trust_env=True) as c: r=c.post(a.base_url.rstrip("/")+"/annotations",json=payload,headers=headers)
        body=r.json(); print(json.dumps({"status":"success" if r.status_code<300 else "error","tool":"hypothesis","http_status":r.status_code,"annotation":body},ensure_ascii=False)); return 0 if r.status_code<300 else 1
    except Exception as exc: print(json.dumps({"status":"error","tool":"hypothesis","message":str(exc)})); return 1
if __name__ == "__main__": raise SystemExit(main())
