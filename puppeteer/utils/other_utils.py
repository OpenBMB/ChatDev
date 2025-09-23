import json
import logging
import re
from time import sleep
from typing import Union

# =============================
# Singleton Decorator
# =============================
def Singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


# =============================
# JSON Formatter Class
# =============================
class JsonFormat:
    def __init__(self, query_func):
        self.query_func = query_func

    def load_json_with_invalid_escape(self, json_str: str) -> dict:
        """Handle invalid JSON escape sequences."""
        json_str = json_str.strip()
        json_str = re.sub(r'(?<!\\)\n', ' ', json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                json_str = re.sub(r'\$begin:math:text$?!["\\\\/bfnrtu])', r'\\\\\\\\', json_str)
                json_str = re.sub(r'(?<!\\$end:math:text$"', '\\"', json_str)
                json_str = f'"{json_str}"'
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {'action': 'Error', 'parameter': 'Invalid JSON format'}

    def json_check(self, text: str) -> tuple[bool, Union[dict, str]]:
        try:
            d = self.load_json_with_invalid_escape(text)
            if isinstance(d, dict) and d.get("action") != "Error":
                return True, d
        except Exception:
            pass
        return False, ""

    def json_reformat(self, text: str, max_try_times: int = 3) -> dict:
        """Reformat GPT text to strict JSON object."""
        prompt_template = """
        Please reformat the given text strictly according to the specified JSON format.
        The given text is: {}.
        The specified JSON format is: {{"action": "", "parameter": ""}}, presented in plain text.
        Only return one JSON object.
        """
        for _ in range(max_try_times):
            text = text.replace("null", '"Error"').replace("None", '"Error"').replace("```json", "").replace("```", "")
            valid, json_obj = self.json_check(text)
            if valid:
                return json_obj
            logging.info(f"Error format:\n{text}")
            text, _ = self.query_func(prompt_template.format(text))
            sleep(1)
        return {'action': 'Error', 'parameter': 'Error'}