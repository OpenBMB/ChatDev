from _liblib import ok,err,a
import dateparser
try:
    d=dateparser.parse(a(1)); ok("lib.dateparser_parse",text=a(1),parsed=d.isoformat() if d else None)
except Exception as ex: err("lib.dateparser_parse",str(ex))
