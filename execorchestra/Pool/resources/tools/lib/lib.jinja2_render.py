from _liblib import ok,err,a
import jinja2,json
try: ok("lib.jinja2_render",rendered=jinja2.Template(a(1)).render(**json.loads(a(2,"{}"))))
except Exception as e: err("lib.jinja2_render",str(e))
