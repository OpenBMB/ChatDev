from _apilib import get, a
get(f"https://rickandmortyapi.com/api/{a(1,'character')}"+(f"/{a(2)}" if a(2) else ""),"rickandmorty")
