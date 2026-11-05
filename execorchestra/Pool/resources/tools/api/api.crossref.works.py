from _apilib import get, a
get("https://api.crossref.org/works","crossref",params={"query":a(1),"rows":"3"})
