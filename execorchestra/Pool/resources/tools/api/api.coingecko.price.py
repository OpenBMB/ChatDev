from _apilib import get, a
get("https://api.coingecko.com/api/v3/simple/price","coingecko",params={"ids":a(1),"vs_currencies":a(2,"usd")})
