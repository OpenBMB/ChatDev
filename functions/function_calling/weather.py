from typing import Any


def get_city_num(city: str, _context: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Fetch the city code for a given city name.

    Example response:
    {
        "city": "Beijing",
        "city_num": 3701,
    }
    """
    if not isinstance(city, str):
        return {"error": "city must be a string"}
    stripped_city = city.strip()
    if not stripped_city:
        return {"error": "city cannot be empty"}

    return {
        "city": stripped_city,
        "city_num": 3701,
    }


def get_weather(
    city_num: int | str,
    unit: str = "celsius",
    _context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fetch weather information for the city represented by ``city_num``.

    Example response:
    {
        "city_num": 3701,
        "temperature": 15,
        "unit": "celsius",
    }
    """
    if isinstance(city_num, bool) or not isinstance(city_num, (int, str)):
        return {"error": "city_num must be an integer"}
    try:
        if isinstance(city_num, str):
            stripped_num = city_num.strip()
            if not stripped_num:
                return {"error": "city_num cannot be empty"}
            resolved_city_num = int(stripped_num)
        else:
            resolved_city_num = int(city_num)
        if resolved_city_num <= 0:
            return {"error": "city_num must be positive"}
    except (ValueError, TypeError):
        return {"error": "city_num must be an integer"}

    if not isinstance(unit, str):
        return {"error": "unit must be a string"}
    normalized_unit = unit.strip().lower()
    temperature_c = 15  # Hardcode the temperature value
    if normalized_unit in ("fahrenheit", "f"):
        temperature = temperature_c * 9 / 5 + 32
        final_unit = "fahrenheit"
    elif normalized_unit in ("celsius", "c"):
        temperature = temperature_c
        final_unit = "celsius"
    else:
        return {
            "error": f"unsupported unit '{unit}', expected 'celsius' or 'fahrenheit'"
        }

    return {
        "city_num": resolved_city_num,
        "temperature": temperature,
        "unit": final_unit,
    }
