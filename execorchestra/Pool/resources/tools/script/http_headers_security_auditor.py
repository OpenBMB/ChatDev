"""S-GAR tool — HTTP security-header audit via requests (https://requests.readthedocs.io, Apache-2.0).
Fetches <url> and checks for the presence of recognized security headers."""
import sys
from _sgar_cli import emit
import requests

SECURITY_HEADERS = [
    "Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
    "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy",
]

if len(sys.argv) < 2:
    print("Usage: python http_headers_security_auditor.py <url>", file=sys.stderr)
    sys.exit(1)
url = sys.argv[1]
if not url.startswith(("http://", "https://")):
    url = "https://" + url
try:
    resp = requests.get(url, timeout=20, allow_redirects=True)
    present = {h: resp.headers.get(h) for h in SECURITY_HEADERS if h in resp.headers}
    missing = [h for h in SECURITY_HEADERS if h not in resp.headers]
    emit({"status": "success", "tool": "requests", "url": resp.url,
          "status_code": resp.status_code, "present_security_headers": present,
          "missing_security_headers": missing,
          "score": f"{len(present)}/{len(SECURITY_HEADERS)}"})
except requests.RequestException as exc:
    emit({"status": "error", "tool": "requests", "url": url,
          "message": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)
