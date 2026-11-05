from _liblib import ok,err,a
import subprocess,json
try:
    r=subprocess.run(["detect-secrets","scan",a(1)],capture_output=True,text=True,timeout=60)
    o=json.loads(r.stdout); ok("lib.detect_secrets",results={k:len(v) for k,v in o.get("results",{}).items()})
except Exception as e: err("lib.detect_secrets",str(e))
