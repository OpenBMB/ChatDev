from _liblib import ok,err,a
from PIL import Image
try:
    im=Image.open(a(1)); op=a(2,"info")
    ok("lib.pillow_transform",operation=op,format=im.format,size=im.size,mode=im.mode)
except Exception as e: err("lib.pillow_transform",str(e))
