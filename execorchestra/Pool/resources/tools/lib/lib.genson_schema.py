from _liblib import ok,err,a
from genson import SchemaBuilder
import json
try:
    b=SchemaBuilder(); b.add_object(json.load(open(a(1)))); ok("lib.genson_schema",schema=b.to_schema())
except Exception as ex: err("lib.genson_schema",str(ex))
