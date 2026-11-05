from _apilib import get, arg
get("https://api.frankfurter.app/latest","frankfurter",params={"from":arg(1,"USD"),"to":arg(2,"EUR")})
