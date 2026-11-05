"""S-GAR tool — CORS header check via requests (https://requests.readthedocs.io, Apache-2.0).
Sends a preflight-style OPTIONS request to <url> and reports the CORS response headers."""
import sys
from _sgar_cli import emit
import requests

CORS_HEADERS = [
    "Access-Control-Allow-Origin", "Access-Control-Allow-Methods",
    "Access-Control-Allow-Headers", "Access-Control-Allow-Credentials",
    "Access-Control-Max-Age",
]

if len(sys.argv) < 2:
    print("Usage: python cors_headers_checker.py <url>", file=sys.stderr)
    sys.exit(1)
url = sys.argv[1]
if not url.startswith(("http://", "https://")):
    url = "https://" + url
try:
    resp = requests.options(url, timeout=20,
                            headers={"Origin": "https://example.com",
                                     "Access-Control-Request-Method": "GET"})
    cors = {h: resp.headers.get(h) for h in CORS_HEADERS if h in resp.headers}
    emit({"status": "success", "tool": "requests", "url": url,
          "status_code": resp.status_code, "cors_enabled": bool(cors),
          "cors_headers": cors})
except requests.RequestException as exc:
    emit({"status": "error", "tool": "requests", "url": url,
          "message": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)
