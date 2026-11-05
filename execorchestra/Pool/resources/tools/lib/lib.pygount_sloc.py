from _liblib import ok,err,a
import subprocess,json
try:
    r=subprocess.run(["pygount","--format=json",a(1)],capture_output=True,text=True,timeout=60)
    ok("lib.pygount_sloc",result=json.loads(r.stdout) if r.stdout.strip() else {"stderr":r.stderr[:200]})
except Exception as e: err("lib.pygount_sloc",str(e))
