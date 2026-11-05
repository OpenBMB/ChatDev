"""Private, job-scoped Playwright reader. No model calls or arbitrary JS API."""
import argparse
import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time
from urllib.parse import urlsplit, urlunsplit


def normalize_url(value):
    p = urlsplit(value)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("public_http_url_required")
    if p.port not in {None, 80, 443}:
        raise ValueError("nonstandard_port_not_allowed")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


def public_host(host):
    if host.lower() in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        return False
    try:
        try:
            records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            if exc.errno != socket.EAI_AGAIN:
                raise
            # Retry transient DNS before dispatching any request to the site.
            time.sleep(0.25)
            records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = [x[4][0] for x in records]
        return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)
    except (ValueError, OSError):
        return False


def page_chunk(page, text_offset=0, link_offset=0):
    """Fit the existing controller's 16 KiB result budget without silent loss."""
    if not 0 <= text_offset <= len(page["text"]) or not 0 <= link_offset <= len(page["links"]):
        raise ValueError("offset_out_of_range")
    text = page["text"][text_offset:text_offset + 5000]
    links = page["links"][link_offset:link_offset + 10]
    def payload():
        t_end, l_end = text_offset + len(text), link_offset + len(links)
        return {**{k:v for k,v in page.items() if k not in {"text", "links"}},
                "text": text, "links": links, "text_offset": text_offset, "link_offset": link_offset,
                "total_text_chars": len(page["text"]), "total_links": len(page["links"]),
                "next_text_offset": t_end if t_end < len(page["text"]) else None,
                "next_link_offset": l_end if l_end < len(page["links"]) else None}
    result = payload()
    while len(json.dumps(result, ensure_ascii=False).encode()) > 14000:
        if len(text) > 1000:
            text = text[:len(text)//2]
        elif links:
            links = links[:-1]
        else:
            raise ValueError("page_metadata_exceeds_budget")
        result = payload()
    return result


def proxy_options(value):
    if not value:
        return None
    from urllib.parse import unquote
    p = urlsplit(value)
    if p.scheme not in {"http", "https", "socks5"} or not p.hostname:
        raise ValueError("invalid_browser_proxy")
    server = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")
    result = {"server":server, "bypass":"localhost,127.0.0.1,::1"}
    if p.username: result["username"] = unquote(p.username)
    if p.password: result["password"] = unquote(p.password)
    return result


def is_access_challenge(title, text):
    probe = (title + " " + text[:500]).lower()
    if any(marker in probe for marker in ("verify you are human", "checking your browser", "just a moment...")):
        return True
    heading = title.partition("|")[0].strip().casefold()
    # Some HTTP 200 interstitials identify themselves in both the title and body.
    return (heading == "verifying your browser"
            and any(line.strip().casefold() == heading for line in text[:500].splitlines())
            and "complete the check below to continue" in text[:500].casefold())


def inline_anchor_targets(text, anchors):
    """Annotate unambiguous visible labels without changing the independent link list."""
    remaining = min(8192, 250000 - len(text))
    if remaining <= 0:
        return text
    inserts = []
    for label, url in anchors:
        if len(inserts) >= 64:
            break
        start = text.find(label)
        if not label or start < 0 or text.find(label, start + 1) >= 0:
            continue
        end = start + len(label)
        if any(start < prior_end and prior_start < end for prior_start, prior_end, _ in inserts):
            continue
        suffix = " (" + url + ")"
        if len(suffix) <= remaining:
            inserts.append((start, end, suffix))
            remaining -= len(suffix)
    for _, end, suffix in sorted(inserts, reverse=True):
        text = text[:end] + suffix + text[end:]
    return text


_LINKS_JS = "els => els.slice(0, 3000).map(e => ({url:e.href,text:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,160)}))"
_INLINE_LINKS_JS = """els => els.slice(0, 3000).map(e => {
    const label = (e.innerText || '').trim();
    return {url:e.href, text:(label || e.getAttribute('aria-label') || '').trim().slice(0,160),
        inline:label.length > 0 && label.length <= 160 && e.checkVisibility({visibilityProperty:true, opacityProperty:true})
            && !e.closest('nav, header, footer, aside, [role=navigation], [role=banner], [role=contentinfo]')
            && !(e.getAttribute('href') || '').trim().startsWith('#')};
})"""


def build_app(state_dir, allowed_hosts=(), *, inline_links=False):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request, HTTPException
    from playwright.async_api import async_playwright
    token = os.environ.get("SGAR_BROWSER_TOKEN", "")
    if len(token) < 24:
        raise ValueError("browser_token_required")
    state = Path(state_dir).resolve()
    state.mkdir(parents=True, exist_ok=False, mode=0o700)
    pages = OrderedDict()
    lock = asyncio.Lock()
    runtime = {}
    allowed = {host.lower() for host in allowed_hosts}

    @asynccontextmanager
    async def lifespan(app):
        async with async_playwright() as pw:
            proxy = proxy_options(os.environ.get("SGAR_TOOL_HTTPS_PROXY"))
            browser = await pw.chromium.launch(headless=True, proxy=proxy)
            runtime["browser"] = browser
            runtime["context"] = await browser.new_context(accept_downloads=False, service_workers="block")
            try:
                yield
            finally:
                await runtime["context"].close()
                await browser.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def auth(request):
        if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    async def health(request: Request):
        auth(request)
        return {"ready": bool(runtime.get("browser")), "cached_pages": len(pages)}

    @app.post("/reset")
    async def reset(request: Request):
        auth(request)
        async with lock:
            await runtime["context"].close()
            runtime["context"] = await runtime["browser"].new_context(accept_downloads=False, service_workers="block")
            pages.clear()
        return {"status":"success"}

    @app.post("/read")
    async def read(request: Request):
        auth(request)
        result = await read_page(request)
        if result.get("status") == "error":
            fields = ("error", "http_status", "error_class")
            print(json.dumps({"event": "page_read_failed", "at": datetime.now(timezone.utc).isoformat(),
                              **result.pop("_diagnostic", {}),
                              **{k: result[k] for k in fields if k in result}}), flush=True)
        return result

    async def read_page(request: Request):
        try:
            if int(request.headers.get("content-length", "0")) > 8192:
                raise ValueError("request_too_large")
            body = await request.json()
            raw_url = body.get("url", "")
            if not isinstance(raw_url, str) or len(raw_url) > 4096:
                raise ValueError("invalid_url")
            url = normalize_url(raw_url)
            host = urlsplit(url).hostname
            if allowed and host not in allowed:
                raise ValueError("navigation_outside_allowed_hosts")
            if not await asyncio.to_thread(public_host, host):
                raise ValueError("public_host_required")
            offsets = [body.get(k, 0) for k in ["text_offset", "link_offset"]]
            if any(type(x) is not int or x < 0 for x in offsets):
                raise ValueError("invalid_offset")
        except (ValueError, TypeError, AttributeError):
            return {"status":"error", "error":"invalid_or_disallowed_request"}
        async with lock:
            if url not in pages:
                if any(offsets):
                    return {"status":"error", "error":"snapshot_expired_restart_at_offset_zero"}
                tab = await runtime["context"].new_page()
                resolved = {}
                navigation_blocked = False
                async def route_guard(route):
                    nonlocal navigation_blocked
                    try:
                        u = normalize_url(route.request.url)
                        h = urlsplit(u).hostname
                        if h not in resolved:
                            resolved[h] = await asyncio.to_thread(public_host, h)
                        permitted = resolved[h]
                        if route.request.is_navigation_request() and allowed:
                            permitted = permitted and h in allowed
                        if not permitted:
                            if route.request.is_navigation_request():
                                navigation_blocked = True
                            await route.abort()
                        elif route.request.resource_type in {"media", "font"}:
                            await route.abort()
                        else:
                            await route.continue_()
                    except (ValueError, OSError):
                        if route.request.is_navigation_request():
                            navigation_blocked = True
                        await route.abort()
                await tab.route("**/*", route_guard)
                phase = "navigation"
                try:
                    response = await tab.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await tab.wait_for_timeout(800)
                    status = response.status if response else None
                    if status is None or status >= 400:
                        return {"status":"error", "error":"page_http_error", "http_status":status}
                    # DOM innerText keeps visible tables and rendered text. It
                    # does not require a second, incompatible extraction stack.
                    phase = "body"
                    text = await tab.locator("body").inner_text(timeout=5000)
                    phase = "links"
                    links = await tab.locator("a[href]").evaluate_all(_INLINE_LINKS_JS if inline_links else _LINKS_JS)
                    valid, seen = [], set()
                    anchors = []
                    for item in links:
                        try: link = normalize_url(item["url"])
                        except ValueError: continue
                        if len(link) > 2048: continue
                        if allowed and urlsplit(link).hostname not in allowed: continue
                        if inline_links and item["inline"] and len(anchors) < 256:
                            anchors.append((item["text"], link))
                        if link in seen: continue
                        seen.add(link)
                        valid.append({"url":link,"text":item["text"]})
                    if not text.strip():
                        return {"status":"error", "error":"empty_readable_content"}
                    phase = "metadata"
                    final_url = normalize_url(tab.url)
                    title = (await tab.title())[:250]
                    if is_access_challenge(title, text):
                        return {"status":"error", "error":"site_access_challenge"}
                    if inline_links:
                        text = inline_anchor_targets(text, anchors)
                    page = {"status":"success", "tool":"browser_read_page", "requested_url":url,
                            "final_url":final_url, "title":title, "http_status":status,
                            "fetched_at":datetime.now(timezone.utc).isoformat(),
                            "page_id":hashlib.sha256((final_url + text).encode()).hexdigest()[:20],
                            "content_truncated":len(text)>250000, "links_truncated":len(links)>=3000,
                            "text":text[:250000], "links":valid, "rendered":True}
                    pages[url] = page
                    while len(pages)>40: pages.popitem(last=False)
                    snapshot = state/(page["page_id"]+'.json')
                    snapshot.write_text(json.dumps(page,ensure_ascii=False),encoding="utf-8")
                    snapshot.chmod(0o600)
                except Exception as exc:
                    # Keep URLs, page content, and raw exception messages out of the log.
                    code = re.search(r"\bnet::(ERR_[A-Z0-9_]+)\b", str(exc))
                    return {"status":"error", "error":"browser_read_failed", "error_class":type(exc).__name__,
                            "_diagnostic":{"phase":phase, "net_error":code.group(1) if code else None,
                                           "navigation_blocked":navigation_blocked}}
                finally:
                    await tab.close()
            try:
                return page_chunk(pages[url], *offsets)
            except ValueError:
                return {"status":"error", "error":"invalid_page_offset_or_size"}
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--allowed-host", action="append", default=[])
    parser.add_argument("--inline-links", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("allocated_job_required")
    import uvicorn
    uvicorn.run(build_app(args.state_dir,args.allowed_host,inline_links=args.inline_links),host="127.0.0.1",port=args.port,
                access_log=False,log_level="warning")


if __name__ == "__main__": main()
