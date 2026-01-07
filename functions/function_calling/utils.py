import time
from typing import Union


def wait(seconds: float):
    """
    Wait for a specified number of seconds.

    Args:
        seconds: The number of seconds to wait.
    """
    if isinstance(seconds, str):  # Convert string to float if necessary
        try:
            if "." in seconds:
                seconds = float(seconds)
            else:
                seconds = int(seconds)
        except ValueError:
            # Fallback to float if int conversion fails or other string formats
            seconds = float(seconds)
    
    time.sleep(seconds)


def get_current_time():
    """
    Get the current time in the format: YYYY-MM-DD HH:MM:SS.
    
    Returns:
        str: The current time in the format: YYYY-MM-DD HH:MM:SS.
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())