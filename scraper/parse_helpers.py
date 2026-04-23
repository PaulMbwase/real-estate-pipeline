# scraper/parse_helpers.py
import re

def parse_year(value: str | None) -> int | None:
    """Extract 4-digit year from a string."""
    if not value:
        return None
    match = re.search(r'\b(19|20)\d{2}\b', value)
    return int(match.group()) if match else None


def parse_float(value: str | None) -> float | None:
    """Extract first numeric value from a string."""
    if not value:
        return None
    # Remove commas, extract first number
    cleaned = value.replace(',', '')
    match = re.search(r'\d+(\.\d+)?', cleaned)
    return float(match.group()) if match else None


def parse_int(value: str | None, max_value: int = 1000) -> int | None:
    """Extract first integer from a string, with sanity cap."""
    if not value:
        return None
    match = re.search(r'\d+', value)
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