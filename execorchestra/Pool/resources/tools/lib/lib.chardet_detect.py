from _liblib import ok,err,a
import chardet
try: ok("lib.chardet_detect",file=a(1),result=chardet.detect(open(a(1),"rb").read()))
except Exception as ex: err("lib.chardet_detect",str(ex))
