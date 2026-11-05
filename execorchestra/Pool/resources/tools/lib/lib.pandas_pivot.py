from _liblib import ok,err,a
import pandas as pd
try:
    df=pd.read_csv(a(1)); p=pd.pivot_table(df,index=a(2),values=a(3),aggfunc="mean")
    ok("lib.pandas_pivot",csv=p.reset_index().to_csv(index=False))
except Exception as e: err("lib.pandas_pivot",str(e))
