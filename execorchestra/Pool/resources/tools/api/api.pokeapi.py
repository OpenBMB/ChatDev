from _apilib import get, arg
get(f"https://pokeapi.co/api/v2/pokemon/{str(arg(1)).lower()}","pokeapi")
