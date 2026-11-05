from _apilib import get, a
get(f"http://ip-api.com/json/{a(1) or ''}".rstrip("/"),"ip_api")
