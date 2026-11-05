from _liblib import ok,err,a
import validators
try:
    k=a(2,"url"); f=getattr(validators,k); ok("lib.validators_check",kind=k,value=a(1),valid=bool(f(a(1))))
except Exception as ex: err("lib.validators_check",str(ex))
