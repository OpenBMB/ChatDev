#!/usr/bin/env python3
"""SGAR adapter for a self-hosted SearXNG JSON search endpoint."""
from __future__ import annotations
import argparse, json, os, sys
from urllib.parse import urljoin
import httpx

# The launcher supplies a project-scoped proxy and explicit local-service
# NO_PROXY entries. Honor those routes, including when the service is remote.

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("query"); p.add_argument("--base-url", default=os.environ.get("SEARXNG_BASE_URL", "http://searxng:8080")); p.add_argument("--categories", default="general"); p.add_argument("--limit", type=int, default=10); p.add_argument("--timeout-ms", type=int, default=15000)
    p.add_argument("--fallback-engines", default="bing,yahoo,mwmbl")
    a = p.parse_args()
    if a.limit < 1 or a.limit > 50 or not a.query.strip():
        print(json.dumps({"status":"error","tool":"searxng","message":"invalid query or limit"})); return 2
    endpoint = urljoin(a.base_url.rstrip("/") + "/", "search")
    try:
        with httpx.Client(timeout=a.timeout_ms / 1000, follow_redirects=False, trust_env=True) as c:
            params = {"q": a.query, "format": "json", "categories": a.categories, "pageno": 1}
            r = c.get(endpoint, params=params)
            body = r.json()
            # Healthy results and legitimate empty searches keep their original
            # behavior. Only explicit engine failure permits one alternate
            # engine request, with the identical query/category. No service
            # restart, CAPTCHA bypass, answer generation or model retry.
            unavailable = body.get("unresponsive_engines") if isinstance(body, dict) else None
            if r.status_code < 400 and isinstance(body, dict) and body.get("results") == [] and unavailable:
                failed = {item[0] for item in unavailable if isinstance(item, list) and item}
                alternatives = [name.strip() for name in a.fallback_engines.split(",")
                                if name.strip() and name.strip() not in failed]
                if alternatives:
                    r = c.get(endpoint, params={**params, "engines": ",".join(alternatives)})
                    body = r.json()
        raw = body.get("results") if isinstance(body, dict) else None
        if r.status_code >= 400 or not isinstance(raw, list):
            print(json.dumps({"status":"error","tool":"searxng","http_status":r.status_code,"message":"invalid SearXNG response","response":body}, ensure_ascii=False)); return 1
        if not raw and body.get("unresponsive_engines"):
            print(json.dumps({"status":"error","tool":"searxng","message":"search engines unavailable; no source records obtained","unresponsive_engines":body["unresponsive_engines"]}, ensure_ascii=False)); return 1
        records=[]
        for rank,item in enumerate(raw[:a.limit],1):
            if not isinstance(item,dict) or not item.get("url"): continue
            records.append({"rank":rank,"title":item.get("title"),"url":item.get("url"),"content":item.get("content"),"engine":item.get("engine"),"category":item.get("category"),"publishedDate":item.get("publishedDate"),"score":item.get("score")})
        print(json.dumps({"status":"success","tool":"searxng","query":a.query,"endpoint":endpoint,"records":records,"result_count":len(records),"raw_engine_count":len(body.get("answers",[])) if isinstance(body,dict) else 0}, ensure_ascii=False)); return 0
    except Exception as exc:
        print(json.dumps({"status":"error","tool":"searxng","message":str(exc)})); return 1
if __name__ == "__main__": raise SystemExit(main())
