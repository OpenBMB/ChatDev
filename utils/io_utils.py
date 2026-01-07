from typing import Any, Dict
import yaml

def read_yaml(path) -> Dict[str, Any]:
    with open(path, mode="r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)