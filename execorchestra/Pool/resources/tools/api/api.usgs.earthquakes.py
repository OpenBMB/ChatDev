from _apilib import get, a
get("https://earthquake.usgs.gov/fdsnws/event/1/query","usgs",params={"format":"geojson","limit":"5","minmagnitude":"4"})
