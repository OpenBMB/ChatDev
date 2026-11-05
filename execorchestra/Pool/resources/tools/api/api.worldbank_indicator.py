from _apilib import get, a
get(f"https://api.worldbank.org/v2/country/{a(1)}/indicator/{a(2)}","worldbank",params={"format":"json","per_page":"5"})
