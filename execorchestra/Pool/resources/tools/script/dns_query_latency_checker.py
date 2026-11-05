"""S-GAR tool — DNS resolution + latency via dnspython (https://www.dnspython.org, ISC).
Resolves the A records for <hostname> and reports query latency."""
import sys
import time
from _sgar_cli import emit
import dns.resolver

if len(sys.argv) < 2:
    print("Usage: python dns_query_latency_checker.py <hostname> [record_type]", file=sys.stderr)
    sys.exit(1)
host = sys.argv[1]
rtype = sys.argv[2] if len(sys.argv) > 2 else "A"
try:
    start = time.perf_counter()
    answers = dns.resolver.resolve(host, rtype)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    emit({"status": "success", "tool": "dnspython", "hostname": host, "record_type": rtype,
          "latency_ms": latency_ms, "records": [r.to_text() for r in answers]})
except dns.exception.DNSException as exc:
    emit({"status": "error", "tool": "dnspython", "hostname": host,
          "message": f"{type(exc).__name__}: {exc}"})
    sys.exit(1)
