from _liblib import ok,err,a
import numpy as np,json
try:
    m=np.array(json.loads(a(1))); op=a(2,"det")
    r={"det":float(np.linalg.det(m))} if op=="det" else {"inv":np.linalg.inv(m).tolist()} if op=="inv" else {"eigvals":np.linalg.eigvals(m).real.tolist()}
    ok("lib.numpy_linalg",operation=op,result=r)
except Exception as ex: err("lib.numpy_linalg",str(ex))
