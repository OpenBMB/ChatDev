import sys, json
def emit(o): print(json.dumps(o, ensure_ascii=False, default=str))
def a(i, d=None): return sys.argv[i] if len(sys.argv) > i else d
def ok(tool, **kw): emit({"status":"success","tool":tool, **kw})
def err(tool, m): emit({"status":"error","tool":tool,"message":m}); sys.exit(1)
