from _liblib import ok,err,a
from pypdf import PdfReader
try:
    r=PdfReader(a(1)); ok("lib.pypdf_merge",pages=len(r.pages),metadata=str(r.metadata)[:300])
except Exception as e: err("lib.pypdf_merge",str(e))
