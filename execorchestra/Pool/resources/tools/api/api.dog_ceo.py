from _apilib import get, a
get(f"https://dog.ceo/api/breed/{a(1)}/images/random" if a(1) else "https://dog.ceo/api/breeds/image/random","dog_ceo")
