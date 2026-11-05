"""Private observational sidecar for the optional open-web research diagnostic."""
import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def url_identity(value):
    """Retain host and join key, without logging URL paths, queries or credentials."""
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
        if p.scheme not in ("http", "https") or not p.hostname or p.username is not None or p.password is not None:
            return None
        host = p.hostname.lower()
        authority = f"[{host}]" if ":" in host else host
        if p.port is not None and p.port != {"http": 80, "https": 443}[p.scheme]:
            authority += f":{p.port}"
        url = urlunsplit((p.scheme, authority, p.path or "/", p.query, ""))
        return {"host": host, "url_id": hashlib.sha256(url.encode()).hexdigest()}
    except (ValueError, UnicodeError):
        return None


def record_navigation(output_dir, arguments, public_content):
    """Record only the projection prepared for the next model turn. Best effort."""
    try:
        obs = json.loads(public_content)
        resource = obs["resource_id"]
        if resource not in {"tool.searxng_search.v1", "tool.browser_read_page.v1"}:
            return
        body = obs.get("public_result")
        body = body if isinstance(body, dict) else {}
        row = {k: obs[k] for k in ("session_id", "turn_id", "observation_id", "status", "resource_id")}
        row["observation_sha256"] = obs["observation_sha256"]
        if resource == "tool.searxng_search.v1":
            records = body.get("records")
            query = arguments.get("query")
            row["query_id"] = hashlib.sha256(query.encode()).hexdigest() if isinstance(query, str) else None
            row["candidates"] = [
                {"rank": item.get("rank"), "title": str(item.get("title") or "")[:512],
                 "url": url_identity(item.get("url"))}
                for item in (records if isinstance(records, list) else []) if isinstance(item, dict)
            ]
            row["complete_list"] = (obs["status"] == "success" and obs.get("public_result_complete", True)
                                    and isinstance(records, list) and len(row["candidates"]) == len(records)
                                    and body.get("result_count") == len(records))
        else:
            row.update(requested=url_identity(arguments.get("url")), final=url_identity(body.get("final_url")),
                       title=str(body.get("title") or "")[:512], text_offset=arguments.get("text_offset", 0),
                       link_offset=arguments.get("link_offset", 0))
        data = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        fd = os.open(Path(output_dir) / "research_navigation.jsonl",
                     os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    except Exception as exc:
        # Diagnostic I/O cannot reject a valid call or trigger a repeat dispatch.
        logging.getLogger(__name__).warning("Navigation observation unavailable (%s)", type(exc).__name__)
