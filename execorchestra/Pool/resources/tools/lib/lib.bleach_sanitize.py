from _liblib import ok,err,a
import bleach
try: ok("lib.bleach_sanitize",clean=bleach.clean(a(1)))
except Exception as e: err("lib.bleach_sanitize",str(e))
