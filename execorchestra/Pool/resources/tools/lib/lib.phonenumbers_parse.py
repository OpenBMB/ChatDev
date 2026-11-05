from _liblib import ok,err,a
import phonenumbers as p
try:
    n=p.parse(a(1),a(2,"US")); ok("lib.phonenumbers_parse",valid=p.is_valid_number(n),country=p.region_code_for_number(n),e164=p.format_number(n,p.PhoneNumberFormat.E164))
except Exception as ex: err("lib.phonenumbers_parse",str(ex))
