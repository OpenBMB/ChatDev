from _liblib import ok,err,a
import sqlglot
try: ok("lib.sqlglot_transpile",result=sqlglot.transpile(a(1),read=a(2,"mysql"),write=a(3,"postgres")))
except Exception as ex: err("lib.sqlglot_transpile",str(ex))
