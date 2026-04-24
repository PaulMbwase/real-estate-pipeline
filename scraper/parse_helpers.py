# scraper/parse_helpers.py
import re

def parse_year(value: str | None) -> int | None:
    """Extract 4-digit year from a string."""
    if not value:
        return None
    match = re.search(r'\b(18|19|20)\d{2}\b', value)
    return int(match.group()) if match else None


def parse_float(value, max_value: float = 1_000_000_000) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace(',', '').replace('$', '').strip()
    match = re.search(r'\d+(\.\d+)?', cleaned)
    if match:
        result = float(match.group())
        return result if result <= max_value else None
    return None


def parse_int(value, max_value: int = 1000) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if int(value) <= max_value else None
    match = re.search(r'\d+', str(value))
    if match:
        result = int(match.group())
        return result if result <= max_value else None
    return None


def parse_bool(value: str | None) -> bool:
    """Return True if value exists and is not explicitly negative."""
    if not value:
        return False
    negative = ['no ', 'none', 'sans', 'aucun']
    return not any(n in value.lower() for n in negative)