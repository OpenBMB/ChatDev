from _apilib import get, a
lang=a(2,"en"); import urllib.parse
get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(a(1))}","wikipedia")
