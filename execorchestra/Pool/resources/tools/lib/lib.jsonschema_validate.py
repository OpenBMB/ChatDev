from _liblib import ok,err,a
import jsonschema,json
try:
    jsonschema.validate(json.load(open(a(1))),json.load(open(a(2)))); ok("lib.jsonschema_validate",valid=True)
except jsonschema.ValidationError as e: ok("lib.jsonschema_validate",valid=False,error=e.message)
except Exception as ex: err("lib.jsonschema_validate",str(ex))
