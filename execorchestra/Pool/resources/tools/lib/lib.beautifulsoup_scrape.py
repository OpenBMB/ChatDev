from _liblib import ok,err,a
from bs4 import BeautifulSoup
try:
    soup=BeautifulSoup(open(a(1),encoding="utf-8").read(),"html.parser")
    ok("lib.beautifulsoup_scrape",matches=[e.get_text(strip=True) for e in soup.select(a(2,"p"))])
except Exception as e: err("lib.beautifulsoup_scrape",str(e))
