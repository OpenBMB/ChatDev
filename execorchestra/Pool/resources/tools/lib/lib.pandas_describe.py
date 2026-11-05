from _liblib import ok,err,a
import pandas as pd
try: ok("lib.pandas_describe",describe=pd.read_csv(a(1)).describe(include="all").to_dict())
except Exception as e: err("lib.pandas_describe",str(e))
