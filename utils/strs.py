def titleize(value: str) -> str:
    sanitized = value.replace("_", " ").replace("-", " ").strip()
    if not sanitized:
        return value
    return " ".join(part.capitalize() for part in sanitized.split())