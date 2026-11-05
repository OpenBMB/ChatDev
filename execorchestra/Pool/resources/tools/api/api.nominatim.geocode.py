from _apilib import get, a
get("https://nominatim.openstreetmap.org/search","nominatim",params={"q":a(1),"format":"json","limit":"3"})
