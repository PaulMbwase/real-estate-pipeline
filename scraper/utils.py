from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import asyncio
import socket

geolocator = Nominatim(user_agent="real-estate-pipeline")

# async def geocode_address(street: str | None, city: str | None) -> dict:
#     """Convert a street address and city into lat/lon coordinates."""
#     if not street and not city:
#         return {"latitude": None, "longitude": None}

#     query = ", ".join(filter(None, [street, city, "Quebec, Canada"]))


def fix_encoding(text: str | None) -> str | None:
    """Attempt to fix common encoding corruption in French text."""
    if not text:
        return None
    try:
        # Try to fix latin-1 misread as cp1252
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

async def geocode_address(address: str | None) -> dict:
    if not address:
        return {"latitude": None, "longitude": None}
    
    clean = fix_encoding(address)
    query = f"{clean}, Quebec, Canada"
    try:
        loop = asyncio.get_event_loop()
        location = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: geolocator.geocode(query, timeout=10)), # type: ignore
            timeout=15
        )
        if location:
            return {"latitude": round(location.latitude, 6), "longitude": round(location.longitude, 6)} # type: ignore
    except (asyncio.CancelledError, asyncio.TimeoutError):
        print(f"  ⚠️ Geocoding timeout: {query}")
    except Exception as e:
        print(f"  ⚠️ Geocoding error: {e}")
    return {"latitude": None, "longitude": None}


async def safe_text(locator) -> str | None:
    """Safely extract text from a locator."""
    try:
        if await locator.count() > 0:
            text = await locator.first.text_content(timeout=5000)
            return " ".join(text.split()) if text else None
        return None
    except Exception:
        return None


async def safe_attr(locator, attr: str) -> str | None:
    """Safely extract an attribute from a locator."""
    try:
        if await locator.count() > 0:
            value = await locator.first.get_attribute(attr, timeout=5000)
            return value.strip() if value else None
        return None
    except Exception:
        return None
    

async def clean_address(address: str | None) -> str | None:
    """Clean raw address string into a single normalized string."""
    if not address:
        return None
    return " ".join(address.split())

# async def clean_address(address: str | None) -> dict:
#     """Parse raw address string into street and city components."""
#     if not address:
#         return {"street": None, "city": None}

#     # Try newline split first
#     parts = [p.strip() for p in address.split('\n') if p.strip()]

#     if len(parts) >= 2:
#         return {"street": parts[0], "city": parts[1]}

#     # Fallback — try comma split
#     parts = [p.strip() for p in address.split(',') if p.strip()]
#     if len(parts) >= 2:
#         return {"street": parts[0], "city": parts[-1]}

#     # Last resort — everything goes to street, city unknown
#     return {"street": parts[0] if parts else None, "city": None}


async def extract_detail(page, label_fr: str, label_en: str) -> str | None:
    """Extract a value near a bilingual label — FR/EN fallback."""
    for label in [label_en, label_fr]:
        loc = page.locator(f"text={label}")
        if await loc.count() > 0:
            try:
                text = await loc.first.locator("xpath=..").inner_text()
                return " ".join(text.split()) if text else None
            except Exception:
                pass
    return None


async def wait_for_network(retries: int = 5) -> None:
    """Wait until network is reachable before continuing."""
    for attempt in range(retries):
        try:
            socket.getaddrinfo("google.com", 80)
            return  # network is up
        except socket.gaierror:
            print(f"  ⚠️ Network down — waiting 15 seconds... ({attempt + 1}/{retries})")
            await asyncio.sleep(15)
    raise RuntimeError("Network unreachable after multiple retries.")