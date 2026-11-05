from _apilib import get, arg
get("https://api.open-meteo.com/v1/forecast","open_meteo",params={"latitude":arg(1),"longitude":arg(2),"current_weather":"true"})
