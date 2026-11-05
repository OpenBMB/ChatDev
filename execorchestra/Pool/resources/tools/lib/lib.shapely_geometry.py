from _liblib import ok,err,a
from shapely import wkt
try:
    g1=wkt.loads(a(1)); op=a(3,"area")
    if op=="area": r=g1.area
    elif op=="intersects": r=g1.intersects(wkt.loads(a(2)))
    elif op=="distance": r=g1.distance(wkt.loads(a(2)))
    else: r=str(g1.centroid)
    ok("lib.shapely_geometry",operation=op,result=str(r))
except Exception as e: err("lib.shapely_geometry",str(e))
