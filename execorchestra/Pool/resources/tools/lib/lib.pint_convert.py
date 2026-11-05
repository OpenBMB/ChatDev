from _liblib import ok,err,a
import pint
try:
    u=pint.UnitRegistry(); q=(float(a(1))*u(a(2))).to(a(3)); ok("lib.pint_convert",value=float(a(1)),result=q.magnitude,unit=str(q.units))
except Exception as ex: err("lib.pint_convert",str(ex))
