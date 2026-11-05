#!/usr/bin/env python3
"""Task-container adapter for upstream Browsertrix Crawler."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, time
from urllib.parse import urlsplit
from urllib.request import proxy_bypass_environment
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("url"); p.add_argument("output_dir"); p.add_argument("--collection",default="capture"); p.add_argument("--timeout-s",type=int,default=180); a=p.parse_args(); out=Path(a.output_dir).resolve(); out.mkdir(parents=True,exist_ok=True); exe=shutil.which("browsertrix-crawler") or shutil.which("crawl")
    if not exe: print(json.dumps({"status":"error","tool":"browsertrix-crawler","message":"browsertrix-crawler not available in task image"})); return 127
    started=time.monotonic()
    cmd=[exe] + ([] if Path(exe).name == "crawl" else ["crawl"])
    cmd += ["--url",a.url,"--collection",a.collection,"--cwd",str(out)]
    child_env=os.environ.copy()
    # Browsertrix uses its own proxy option, not HTTP_PROXY. Keep credentials
    # out of argv and honor the launcher's explicit local-service exclusions.
    parsed=urlsplit(a.url)
    proxy=child_env.get("HTTPS_PROXY" if parsed.scheme == "https" else "HTTP_PROXY")
    if proxy:
        bypass=proxy_bypass_environment(parsed.hostname or "", {"no":child_env.get("NO_PROXY", "")})
        child_env["PROXY_SERVER"]="" if bypass else proxy
        child_env.pop("PROXY_HOST",None); child_env.pop("PROXY_PORT",None)
    try: r=subprocess.run(cmd,capture_output=True,text=True,timeout=a.timeout_s,check=False,env=child_env)
    except subprocess.TimeoutExpired: print(json.dumps({"status":"timeout","tool":"browsertrix-crawler"})); return 124
    files=[str(x) for x in out.rglob("*") if x.is_file()]; payload={"status":"success" if r.returncode==0 else "error","tool":"browsertrix-crawler","url":a.url,"output_dir":str(out),"produced_files":files,"exit_code":r.returncode,"stdout":r.stdout,"stderr":r.stderr,"latency_ms":int((time.monotonic()-started)*1000)}; print(json.dumps(payload,ensure_ascii=False)); return 0 if r.returncode==0 else r.returncode
if __name__ == "__main__": raise SystemExit(main())
