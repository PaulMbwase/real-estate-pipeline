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


def normalize_property_type(category: str | None) -> str | None:
    """Normalize raw category into clean property type."""
    if not category:
        return None
    
    cat = category.lower()

    if "quintuplex" in cat:                return "quintuplex"
    if "quadruplex" in cat:                return "quadruplex"
    if "triplex" in cat:                   return "triplex"
    if "duplex" in cat:                    return "duplex"
    if "loft" in cat or "studio" in cat:   return "loft_studio"
    if "condominium house" in cat:         return "condominium_house"
    if "condo" in cat:                     return "condo"
    if "cottage" in cat:                   return "cottage"
    if "hobby farm" in cat:                return "hobby_farm"
    if "mobile home" in cat:               return "mobile_home"
    if "house" in cat:                     return "house"
    if "lot" in cat or "land" in cat:      return "land"
    if "commercial" in cat:                return "commercial"
    if "office" in cat:                    return "office"
    if "industrial" in cat:                return "industrial"

    return None


def normalize_transaction_type(category: str | None) -> list[str]:
    """Extract transaction type(s) from raw category string."""
    if not category:
        return ["for_sale"]
    cat = category.lower()
    if "for sale or for rent" in cat or "for rent or for sale" in cat:
        return ["for_sale", "for_rent"]
    if "for rent" in cat:
        return ["for_rent"]
    return ["for_sale"]