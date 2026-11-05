from _apilib import get, a
get("https://dns.google/resolve","google_dns",params={"name":a(1),"type":a(2,"A")})
