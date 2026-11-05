from _liblib import ok,err,a
import pdfplumber
try:
    with pdfplumber.open(a(1)) as pdf:
        ok("lib.pdfplumber_extract",pages=len(pdf.pages),text="\n".join((p.extract_text() or "") for p in pdf.pages)[:800])
except Exception as e: err("lib.pdfplumber_extract",str(e))
