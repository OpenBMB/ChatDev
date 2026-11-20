"""Unit tests for general utility function tools (wait and get_current_time)."""

import re
from unittest.mock import patch

import pytest

from functions.function_calling.utils import get_current_time, wait
from utils.function_catalog import get_function_catalog


def test_wait_normal_numeric() -> None:
    with patch("time.sleep") as mock_sleep:
        res_zero = wait(0)
        assert res_zero == "Successfully waited for 0 second(s)."
        mock_sleep.assert_called_with(0.0)

        res_float = wait(0.05)
        assert res_float == "Successfully waited for 0.05 second(s)."
        mock_sleep.assert_called_with(0.05)


def test_wait_string_coercion() -> None:
    with patch("time.sleep") as mock_sleep:
        res_str_int = wait(" 2 ")
        assert res_str_int == "Successfully waited for 2 second(s)."
        mock_sleep.assert_called_with(2.0)

        res_str_float = wait("0.125")
        assert res_str_float == "Successfully waited for 0.125 second(s)."
        mock_sleep.assert_called_with(0.125)

        res_sci = wait("1e-2")
        assert res_sci == "Successfully waited for 0.01 second(s)."
        mock_sleep.assert_called_with(0.01)


def test_wait_rejects_bool() -> None:
    with pytest.raises(TypeError, match="must be a number, not a boolean"):
        wait(True)

    with pytest.raises(TypeError, match="must be a number, not a boolean"):
        wait(False)


def test_wait_rejects_none_and_invalid_types() -> None:
    with pytest.raises(TypeError, match="cannot be None"):
        wait(None)

    with pytest.raises(TypeError, match="must be a number, got list"):
        wait([1, 2])

    with pytest.raises(TypeError, match="must be a number, got dict"):
        wait({"seconds": 5})


def test_wait_rejects_empty_and_invalid_strings() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        wait("")

    with pytest.raises(ValueError, match="cannot be empty"):
        wait("   ")

    with pytest.raises(ValueError, match="Invalid wait duration"):
        wait("abc")

    with pytest.raises(ValueError, match="Invalid wait duration"):
        wait("12.34.56")


def test_wait_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        wait(-1)

    with pytest.raises(ValueError, match="must be non-negative"):
        wait("-0.01")


def test_wait_rejects_nan_and_inf() -> None:
    with pytest.raises(ValueError, match="must be a finite number"):
        wait(float("nan"))

    with pytest.raises(ValueError, match="must be a finite number"):
        wait(float("inf"))

    with pytest.raises(ValueError, match="must be a finite number"):
        wait(float("-inf"))


def test_wait_exceeds_max_seconds() -> None:
    with pytest.raises(ValueError, match="exceeds the maximum limit of 300"):
        wait(300.1)

    with pytest.raises(ValueError, match="exceeds the maximum limit of 5"):
        wait(5.5, _max_seconds=5)

    with patch.dict("os.environ", {"MAX_WAIT_SECONDS": "10"}), pytest.raises(
        ValueError, match="exceeds the maximum limit of 10"
    ):
        wait(10.5)


def test_wait_invalid_max_seconds() -> None:
    with pytest.raises(TypeError, match="_max_seconds must be a number"):
        wait(1, _max_seconds="invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="_max_seconds must be a number"):
        wait(1, _max_seconds=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="_max_seconds must be a non-negative finite number"):
        wait(1, _max_seconds=-1)

    with pytest.raises(ValueError, match="_max_seconds must be a non-negative finite number"):
        wait(1, _max_seconds=float("nan"))


def test_get_current_time_format_and_defaults() -> None:
    time_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    # Default invocation
    res_default = get_current_time()
    assert time_pattern.match(res_default) is not None

    # Explicit local
    res_local = get_current_time("local")
    assert time_pattern.match(res_local) is not None

    # Explicit uppercase local
    res_local_upper = get_current_time("LOCAL")
    assert time_pattern.match(res_local_upper) is not None

    # UTC
    res_utc = get_current_time("utc")
    assert time_pattern.match(res_utc) is not None


def test_get_current_time_validation() -> None:
    with pytest.raises(TypeError, match="timezone must be a string"):
        get_current_time(123)

    with pytest.raises(ValueError, match="Unsupported timezone 'invalid'"):
        get_current_time("invalid")


def test_function_catalog_integration() -> None:
    catalog = get_function_catalog()
    catalog.refresh()

    wait_meta = catalog.get("wait")
    assert wait_meta is not None
    assert "seconds" in wait_meta.parameters_schema.get("properties", {})
    assert "seconds" in wait_meta.parameters_schema.get("required", [])
    # Ensure ceiling parameter is not exposed to model tool arguments
    assert "max_seconds" not in wait_meta.parameters_schema.get("properties", {})
    assert "_max_seconds" not in wait_meta.parameters_schema.get("properties", {})

    time_meta = catalog.get("get_current_time")
    assert time_meta is not None
    assert "timezone" in time_meta.parameters_schema.get("properties", {})
