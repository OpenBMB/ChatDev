def get_city_num(city: str) -> dict:
    """
    Fetch the city code for a given city name.
    Example response:
    {
        "city": "Beijing",
        "city_num": "1010",
    }
    """
    return {
        "city_num": 3701
    }

def get_weather(city_num: int, unit: str = "celsius") -> dict:
    """
    Fetch weather information for the city represented by ``city_num``.
    Example response:
    {
        "city_num": "1010",
        "temperature": 20,
        "unit": "celsius"
    }
    """
    temperature_c = 15  # Hardcode the temperature value
    if unit == "fahrenheit":
        temperature = temperature_c * 9 / 5 + 32
    else:
        temperature = temperature_c

    return {
        "city_num": city_num,
        "temperature": temperature,
        "unit": unit
    }
