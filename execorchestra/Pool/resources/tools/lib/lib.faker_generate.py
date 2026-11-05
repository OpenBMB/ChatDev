from _liblib import ok,err,a
from faker import Faker
try:
    f=Faker(); n=int(a(2,"3")); ok("lib.faker_generate",records=[{"name":f.name(),"email":f.email(),"address":f.address()} for _ in range(n)])
except Exception as ex: err("lib.faker_generate",str(ex))
