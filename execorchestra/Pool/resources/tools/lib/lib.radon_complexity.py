from _liblib import ok,err,a
from radon.complexity import cc_visit
try:
    src=open(a(1)).read(); ok("lib.radon_complexity",blocks=[{"name":b.name,"complexity":b.complexity} for b in cc_visit(src)])
except Exception as ex: err("lib.radon_complexity",str(ex))
