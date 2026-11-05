from _apilib import get, a
get("https://api.stackexchange.com/2.3/search","stackexchange",params={"intitle":a(1),"site":a(2,"stackoverflow"),"order":"desc","sort":"votes"})
