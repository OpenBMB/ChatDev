from _liblib import ok,err,a
import qrcode,io,base64
try:
    img=qrcode.make(a(1)); buf=io.BytesIO(); img.save(buf); ok("lib.qrcode_generate",data=a(1),png_base64_len=len(base64.b64encode(buf.getvalue())))
except Exception as ex: err("lib.qrcode_generate",str(ex))
