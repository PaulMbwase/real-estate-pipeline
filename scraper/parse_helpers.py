# scraper/parse_helpers.py
import re

# Known cities and suburbs in Quebec for fallback detection
KNOWN_CITIES = {
    # Montreal Island
    "montréal", "montreal",
    "kirkland", "hampstead", "westmount", "beaconsfield", "dorval",
    "côte-saint-luc", "cote-saint-luc", "mont-royal", "town of mount-royal",
    "pointe-claire", "dollard-des-ormeaux", "dollard des ormeaux",
    "saint-leonard", "saint leonard", "verdun", "lachine", "lasalle",
    "anjou", "outremont", "montreal-nord", "montréal-nord",
    "pierrefonds", "roxboro", "saint-laurent", "côte-des-neiges",
    "notre-dame-de-grâce", "ndg", "rivière-des-prairies",
    "pointe-aux-trembles", "montreal-est", "montréal-est",
    # Laval
    "laval", "chomedey", "vimont", "auteuil", "duvernay",
    "saint-vincent-de-paul", "laval-des-rapides", "pont-viau",
    "sainte-rose", "fabreville", "laval-ouest", "îles-laval",
    # South Shore
    "longueuil", "brossard", "saint-lambert", "greenfield park",
    "saint-bruno", "saint-bruno-de-montarville", "boucherville",
    "saint-hubert", "lemoyne", "saint-basile-le-grand",
    # North Shore
    "terrebonne", "blainville", "mirabel", "repentigny",
    "mascouche", "saint-jerome", "saint-jérôme", "boisbriand",
    "rosemère", "rosemere", "sainte-thérèse", "sainte-therese",
    # Quebec City
    "québec", "quebec", "lévis", "levis", "sainte-foy",
    "sillery", "cap-rouge", "charlesbourg", "beauport",
    "limoilou", "haute-saint-charles", "laurentien",
    # Gatineau
    "gatineau", "hull", "aylmer", "buckingham", "masson-angers",
    # Sherbrooke
    "sherbrooke", "rock forest", "saint-élie-d'orford",
    # Trois-Rivières
    "trois-rivières", "trois-rivieres", "cap-de-la-madeleine",
    "shawinigan",
    # Other major cities
    "granby", "drummondville", "saint-jean-sur-richelieu",
    "salaberry-de-valleyfield", "saint-hyacinthe", "joliette",
    "sept-îles", "rouyn-noranda", "alma", "chicoutimi",
    "jonquière", "jonquiere", "baie-comeau",
    "baie-d'urfé", "baie-d-urfe", "baie d'urfé",
    "sainte-anne-de-bellevue", "senneville", "hudson",
    "vaudreuil-dorion", "vaudreuil", "dorion",
    "saint-lazare", "rigaud", "coteau-du-lac",
    "châteauguay", "chateauguay", "candiac", "delson",
    "sainte-catherine", "saint-constant", "laprairie",
    "varennes", "verchères", "contrecoeur",
    "mont-saint-hilaire", "beloeil", "mcmasterville",
    "otterburn-park", "carignan", "chambly",
    "saint-basile-le-grand", "sainte-julie",
}
STREET_TYPE_MAP = {
    "st":        "rue",
    "str":       "rue",
    "street":    "rue",
    "rue":       "rue",
    "av":        "avenue",
    "ave":       "avenue",
    "avenue":    "avenue",
    "blvd":      "boulevard",
    "boul":      "boulevard",
    "boulevard": "boulevard",
    "ch":        "chemin",
    "chemin":    "chemin",
    "pl":        "place",
    "place":     "place",
    "cres":      "croissant",
    "croissant": "croissant",
    "dr":        "drive",
    "drive":     "drive",
    "rd":        "road",
    "road":      "road",
    "crt":       "court",
    "court":     "court",
    "terr":      "terrasse",
    "terrasse":  "terrasse",
    "montee":    "montée",
    "montée":    "montée",
    "rang":      "rang",
    "rte":       "route",
    "route":     "route",
    "crescent":  "crescent",
    "cres":      "crescent",
    "cr":        "crescent",
    "square":    "square",
    "sq":        "square",
    "pkwy":      "parkway",
    "parkway":   "parkway",
    "promenade": "promenade",
    "prom":      "promenade",
    "côte":      "côte",
    "cote":      "côte",
    "impasse":   "impasse",
    "passage":   "passage",
    "allée":     "allée",
    "allee":     "allée",
    "carré":     "carré",
    "carre":     "carré",
}

STREET_NAME_MAP = {
    "st":        "saint",
    "ste":       "sainte",
    "saint":     "saint",
    "sainte":    "sainte",
    "mt":        "mont",
    "mont":      "mont",
}

def normalize_street_type(word: str) -> str:
    return STREET_TYPE_MAP.get(word.lower().strip("."), word.lower())

def normalize_street_name(name: str) -> str:
    words = name.lower().split("-")
    return "-".join(STREET_NAME_MAP.get(w, w) for w in words)

def parse_address(raw: str | None) -> dict:
    if not raw:
        return {}

    result = {
        "civic_number": None,
        "unit_number":  None,
        "street_name":  None,
        "street_type":  None,
        "borough":      None,
        "city":         None,
        "address":  raw.strip(),
    }

    text = raw.strip()

    # 1 — Extract borough from parentheses — e.g. "Montréal (Outremont)"
    borough_match = re.search(r'\(([^)]+)\)', text)
    if borough_match:
        result["borough"] = borough_match.group(1).strip()
        text = (text[:borough_match.start()] + text[borough_match.end():]).strip()

    # 2 — Extract unit/apt number
    unit_match = re.search(
            r'(?:,\s*|\s+)(apt\.?|app\.?|unit|#|lot|suite|bureau)\s*([\w-]+)',
            text, re.IGNORECASE
        )
    if unit_match:
        result["unit_number"] = unit_match.group(2).strip()
        text = (text[:unit_match.start()] + text[unit_match.end():]).strip()

    # 3 — Extract civic number — handles "353", "353-355", "9635B", "353 - 355A"
    civic_match = re.match(r'^\s*(\d+\w*(?:\s*-\s*\d+\w*)?)\s*,?\s*', text)
    if civic_match:
        result["civic_number"] = re.sub(r'\s+', '', civic_match.group(1))
        text = text[civic_match.end():].strip()

    # 4 — Detect known city at end of remaining text
    # Try progressively shorter suffixes to find a known city
    words = text.split()
    city_found = False
    for n in range(min(4, len(words)), 0, -1):
        candidate = "-".join(words[-n:]).lower()
        candidate_plain = " ".join(words[-n:]).lower()
        if candidate in KNOWN_CITIES or candidate_plain in KNOWN_CITIES:
            result["city"] = " ".join(words[-n:])
            text = " ".join(words[:-n]).strip().rstrip(",").strip()
            city_found = True
            break

    # 5 — Parse street type and name from remaining text
    # e.g. "Rue Saint-Jacques", "Avenue Pratt", "Chemin Minden", "Nassau Street"
    parts = text.strip().split()
    if len(parts) >= 2:
        # Street type first — e.g. "Rue Saint-Jacques"
        if normalize_street_type(parts[0]) in STREET_TYPE_MAP.values():
            result["street_type"] = normalize_street_type(parts[0])
            result["street_name"] = normalize_street_name(
                " ".join(parts[1:]).lower()
            )
        # Street type last — e.g. "Nassau Street", "Minden Chemin"
        elif normalize_street_type(parts[-1]) in STREET_TYPE_MAP.values():
            result["street_type"] = normalize_street_type(parts[-1])
            result["street_name"] = normalize_street_name(
                " ".join(parts[:-1]).lower()
            )
        else:
            # No recognizable street type — store full remaining as street_name
            result["street_name"] = normalize_street_name(text.lower())
    elif len(parts) == 1:
        result["street_name"] = normalize_street_name(parts[0].lower())

    # 6 — If borough found but no city, city is likely Montréal
    if result["borough"] and not result["city"]:
        result["city"] = None

    return result


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

def safe_truncate(value: str | None, max_length: int = 255) -> str | None:
    """Truncate string to max_length to prevent DB overflow."""
    if not value:
        return None
    return value[:max_length]


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
    if "restaurant" in cat:                return "restaurant"
    if "business" in cat:                return "business"
    if "warehouse" in cat:                return "warehouse"
    if "building" in cat:                return "building"
    if "retail" in cat:                return "retail"

    return cat.replace(" for sale", "").replace(" for rent", "").strip().replace(" ", "_")


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

def parse_commercial_price(price_str: str | None) -> dict:
    """Parse commercial rental price string.
    e.g. '$1 /year /square foot' → {price: 1.0, rent_per_sqft: 1.0, rent_period: 'yearly'}
    """
    if not price_str:
        return {"price": None, "rent_per_sqft": None, "rent_period": None}

    result = {"price": None, "rent_per_sqft": None, "rent_period": None}

    # Extract numeric value
    match = re.search(r'[\d,]+\.?\d*', price_str.replace(",", ""))
    if match:
        result["price"] = float(match.group())

    # Detect per sqft pricing
    if "square foot" in price_str.lower() or "sq" in price_str.lower():
        result["rent_per_sqft"] = result["price"]

    # Detect period
    if "year" in price_str.lower():
        result["rent_period"] = "yearly"
    elif "month" in price_str.lower():
        result["rent_period"] = "monthly"

    return result