"""Unit tests for weather function tools."""

from functions.function_calling.weather import get_city_num, get_weather


def test_get_city_num_valid():
    res = get_city_num("Beijing")
    assert res == {"city": "Beijing", "city_num": 3701}


def test_get_city_num_strip_whitespace():
    res = get_city_num("  Shanghai  \n")
    assert res == {"city": "Shanghai", "city_num": 3701}


def test_get_city_num_invalid_types():
    assert get_city_num(None) == {"error": "city must be a string"}
    assert get_city_num(123) == {"error": "city must be a string"}
    assert get_city_num(["Beijing"]) == {"error": "city must be a string"}
    assert get_city_num("") == {"error": "city cannot be empty"}
    assert get_city_num("   \n\t  ") == {"error": "city cannot be empty"}


def test_get_city_num_with_context():
    res = get_city_num("Tokyo", _context={"user": "test"})
    assert res == {"city": "Tokyo", "city_num": 3701}


def test_get_weather_celsius_default():
    res = get_weather(3701)
    assert res == {
        "city_num": 3701,
        "temperature": 15,
        "unit": "celsius",
    }


def test_get_weather_fahrenheit():
    res = get_weather(3701, unit="fahrenheit")
    assert res == {
        "city_num": 3701,
        "temperature": 59.0,
        "unit": "fahrenheit",
    }

    res_upper = get_weather(3701, unit="FAHRENHEIT")
    assert res_upper["temperature"] == 59.0
    assert res_upper["unit"] == "fahrenheit"


def test_get_weather_short_units():
    assert get_weather(3701, unit="c")["unit"] == "celsius"
    assert get_weather(3701, unit="f")["unit"] == "fahrenheit"
    assert get_weather(3701, unit="C")["unit"] == "celsius"
    assert get_weather(3701, unit="F")["unit"] == "fahrenheit"


def test_get_weather_string_city_num_coercion():
    res = get_weather("3701")
    assert res == {
        "city_num": 3701,
        "temperature": 15,
        "unit": "celsius",
    }


def test_get_weather_invalid_city_num():
    assert get_weather(True) == {"error": "city_num must be an integer"}
    assert get_weather(False) == {"error": "city_num must be an integer"}
    assert get_weather(None) == {"error": "city_num must be an integer"}
    assert get_weather("invalid") == {"error": "city_num must be an integer"}
    assert get_weather("") == {"error": "city_num cannot be empty"}
    assert get_weather("   ") == {"error": "city_num cannot be empty"}
    assert get_weather(0) == {"error": "city_num must be positive"}
    assert get_weather(-10) == {"error": "city_num must be positive"}
    assert get_weather(3.14) == {"error": "city_num must be an integer"}


def test_get_weather_invalid_unit():
    assert get_weather(3701, unit=123) == {"error": "unit must be a string"}
    assert get_weather(3701, unit="kelvin") == {
        "error": "unsupported unit 'kelvin', expected 'celsius' or 'fahrenheit'"
    }


def test_get_weather_with_context():
    res = get_weather(3701, _context={"session_id": "session_123"})
    assert res == {
        "city_num": 3701,
        "temperature": 15,
        "unit": "celsius",
    }
