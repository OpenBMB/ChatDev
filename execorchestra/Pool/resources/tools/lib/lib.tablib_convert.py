from _liblib import ok,err,a
import tablib
try:
    ds=tablib.Dataset().load(open(a(1),encoding="utf-8").read()); to=a(2,"json")
    ok("lib.tablib_convert",output=ds.export(to)[:800])
except Exception as e: err("lib.tablib_convert",str(e))
