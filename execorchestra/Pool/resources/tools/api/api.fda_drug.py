from _apilib import get, a
get("https://api.fda.gov/drug/label.json","fda",params={"search":a(1),"limit":"1"})
