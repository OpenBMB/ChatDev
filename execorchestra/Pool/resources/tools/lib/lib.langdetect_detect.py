from _liblib import ok,err,a
from langdetect import detect_langs
try: ok("lib.langdetect_detect",text=a(1)[:60],languages=[str(x) for x in detect_langs(a(1))])
except Exception as ex: err("lib.langdetect_detect",str(ex))
