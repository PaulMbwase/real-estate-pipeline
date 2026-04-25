# scraper/scraper.py

import json
from datetime import datetime 
from playwright.async_api import Page
from scraper.utils import *
from scraper.parse_helpers import *
from dotenv import load_dotenv
import os
import re
import random
import asyncio

load_dotenv()

BASE_URL = os.getenv("BASE_URL")


async def handle_cookies(page: Page) -> None:
    """Accept cookie consent popup if present."""
    try:
        await page.wait_for_selector(
            "button:has-text('Accept'), button:has-text('Accepter')",
            timeout=5000
        )
        await page.locator(
            "button:has-text('Accept'), button:has-text('Accepter')"
        ).first.click()
        print("Cookie consent accepted.")
    except Exception:
        print("No cookie popup found — continuing.")

async def human_delay(min_sec: float = 1.5, max_sec: float = 5.0) -> None:
    """Simulate human-like pause between actions."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def safe_goto(page: Page, url: str, retries: int = 3) -> bool:
    """Navigate with retry logic for network failures."""
    for attempt in range(retries):
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            return True
        except Exception as e:
            print(f"  ⚠️ Navigation failed (attempt {attempt + 1}/{retries}): {e}")
            await asyncio.sleep(5 * (attempt + 1))  # 5s, 10s, 15s
    return False

async def extract_coordinates(page: Page) -> dict:
    """Extract lat/lon directly from schema.org metadata."""
    try:
        lat = await page.locator("meta[itemprop='latitude']").get_attribute("content")
        lon = await page.locator("meta[itemprop='longitude']").get_attribute("content")
        if lat and lon:
            return {
                "latitude":  round(float(lat), 6),
                "longitude": round(float(lon), 6)
            }
    except Exception:
        pass
    return {"latitude": None, "longitude": None}

async def extract_characteristics(page: Page) -> dict:
    """Dynamically extract all carac-container key-value pairs."""
    result = {}
    try:
        containers = page.locator(".carac-container")
        count = await containers.count()

        for i in range(count):
            container = containers.nth(i)
            title = await safe_text(container.locator(".carac-title"))
            value = await safe_text(container.locator(".carac-value"))

            if not title or not value:
                continue

            key = (
                title.strip()
                .lower()
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("/", "_")
                .replace("-", "_")
                .replace("'", "")
            )
            result[key] = value.strip()

    except Exception as e:
        print(f"  ⚠️ Characteristics error: {e}")

    return result

async def get_listings_from_page(page: Page) -> list[dict]:
    
    current_url = page.url
    if "captcha" in current_url or "blocked" in current_url:
        print("⚠️ Blocked — pausing for 60 seconds...")
        await asyncio.sleep(60)
        return []
    try:
        await page.wait_for_selector(
            "[class*='property-thumbnail-item']",
            timeout=10000
        )
    except Exception:
        print("  ⚠️ No listings found on this page — skipping.")
        return []

    cards = page.locator("[class*='property-thumbnail-item']")
    count = await cards.count()
    print(f"Listings found on page: {count}")

    listings = []
    for i in range(count):
        card         = cards.nth(i)
        raw_address  = await safe_text(card.locator("[class*='address']"))
        address      = await clean_address(raw_address)
        price        = await safe_text(card.locator("[class*='price']"))
        property_url = await safe_attr(card.locator("a"), "href")
        property_id  = property_url.split('/')[-1] if property_url else None

        # Extract coordinates from card if available
        lat_lng = card.locator("[data-lat]")
        card_lat = await safe_attr(lat_lng, "data-lat")
        card_lng = await safe_attr(lat_lng, "data-lng")

        listings.append({
            "property_id":  property_id,
            "category":     await safe_text(card.locator("[class*='category']")),
            "price":        price if price and "$" in price else None,
            "address":      address,
            "bedrooms":     await safe_text(card.locator("[class*='cac']")),
            "bathrooms":    await safe_text(card.locator("[class*='sdb']")),
            "property_url": f"{BASE_URL}" + property_url if property_url else None,
            "card_latitude":  float(card_lat) if card_lat else None,
            "card_longitude": float(card_lng) if card_lng else None
        })
    
    await human_delay()
    return listings

async def enrich_listing(page: Page, url: str) -> dict:
    await page.goto(url)
    await page.wait_for_load_state("networkidle")
    await human_delay()
    

    coords    = await extract_coordinates(page)
    chars     = await extract_characteristics(page)
    financial = await extract_financial_details(page)

    return {
        "size_sqft":            await extract_detail(page, "Superficie habitable", "Living area"),
        "year_built":           await extract_detail(page, "Année de construction", "Year built"),
        "broker":               await extract_detail(page, "Courtier", "Real estate broker"),
        "total_rooms":          await extract_detail(page, "Pièces", "Rooms"),
        "garage":               await extract_detail(page, "Garage", "Garage"),
        "pool":                 await extract_detail(page, "Piscine", "Pool"),
        "lot_size":             await extract_detail(page, "Superficie du terrain", "Lot area"),
        "floors":               await extract_detail(page, "Étages", "Floors"),
        "description":          await safe_text(page.locator("[itemprop='description']")),
        "images":               await get_images(page),
        "half_bathrooms":       await extract_detail(page, "Salles d'eau", "Powder rooms"),
        "parking":              await extract_detail(page, "Stationnements", "Parking"),
        "basement":             await extract_detail(page, "Sous-sol", "Basement"),
        "condo_fees":           await extract_detail(page, "Frais de copropriété", "Co-ownership fees"),
        "floor_number":         await extract_detail(page, "Étage", "Floor"),
        "locker":               await extract_detail(page, "Casier", "Locker"),
        "units":                await extract_detail(page, "Logements", "Units"),
        "rental_income":        await extract_detail(page, "Revenus", "Revenue"),
        "zoning":               await extract_detail(page, "Zonage", "Zoning"),
        "ceiling_height":       await extract_detail(page, "Hauteur sous plafond", "Ceiling height"),
        "chars":                chars,
        **financial
    }


async def save_raw(property_id: str, data: dict) -> None:
    """Save raw scraped data to data/raw/ as JSON."""
    os.makedirs("data/raw", exist_ok=True)
    filepath = f"data/raw/{property_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

async def get_images(page: Page) -> list[str]:
    """Extract all image URLs from data-photo-urls attribute."""
    try:
        container = page.locator("#property-roomvo-data")
        if await container.count() == 0:
            # Fallback — primary image only
            img = page.locator("img[itemprop='image']")
            if await img.count() > 0:
                src = await img.first.get_attribute("src")
                return [src] if src else []
            return []

        raw = await container.get_attribute("data-photo-urls")
        if not raw:
            return []

        # Split comma-separated URLs and clean HTML entities
        urls = [url.strip().replace("&amp;", "&") for url in raw.split(",") if url.strip()]
        return urls

    except Exception:
        return []
############################
############################
async def get_total_pages(page: Page) -> int:
    """Extract total number of pages from pager."""
    pager = page.locator("#divPagerBottom li.pager-current")
    text  = await pager.text_content()
    match = re.search(r'\d+\s*/\s*(\d+)', text) # type: ignore
    return int(match.group(1)) if match else 1

# async def paginate(page: Page) -> bool:
#     """Click next page button. Returns True if successful, False if no more pages."""
#     try:
#         # ----------------------------
#         # 1. Get pager info
#         # ----------------------------
#         pager = page.locator("#divPagerBottom li.pager-current")

#         if await pager.count() == 0:
#             print("No pager found.")
#             return False

#         pager_text = (await pager.text_content() or "").strip()
#         print(f"  [Pager] {pager_text}")

#         # ----------------------------
#         # 2. Parse page numbers
#         # ----------------------------
#         match = re.search(r'(\d+)\s*/\s*(\d+)', pager_text)
#         if not match:
#             print("Could not parse pager.")
#             return False

#         current = int(match.group(1))
#         total   = int(match.group(2))

#         if current >= total:
#             print(f"No more pages — {current}/{total}.")
#             return False

#         # ----------------------------
#         # 3. Locate NEXT button (anchor inside li)
#         # ----------------------------
#         next_button = page.locator("#divPagerBottom li.next a").first

#         if await next_button.count() == 0:
#             print("Next button not found.")
#             return False

#         # ----------------------------
#         # 4. Wait for it to be clickable
#         # ----------------------------
#         await next_button.wait_for(state="visible", timeout=5000)

#         # ----------------------------
#         # 5. Click safely
#         # ----------------------------
#         await next_button.click()

#         # ----------------------------
#         # 6. Wait for new content (RELIABLE way)
#         # ----------------------------
#         await page.wait_for_load_state("networkidle")

#         await page.wait_for_selector(
#             "[class*='property-thumbnail-item']",
#             timeout=15000
#         )

#         print(f"  → Moved to page {current + 1}/{total}")
#         return True

#     except Exception as e:
#         print(f"Pagination error: {e}")
#         return False
# ????????????????????????????????????????????????????????????????????
# async def paginate(page: Page) -> bool:
#     """Click next page button. Returns True if successful, False if no more pages."""
#     try:
#         # Read current page info e.g. "2 / 250 +"
#         pager = page.locator("#divPagerBottom li.pager-current")
#         if await pager.count() == 0:
#             print("No pager found.")
#             return False

#         pager_text = await pager.text_content()
#         print(f"  [Pager] {pager_text.strip()}") # type: ignore

#         # Parse "2 / 250 +" → current=2, total=250
#         import re
#         match = re.search(r'(\d+)\s*/\s*(\d+)', pager_text) # type: ignore
#         if not match:
#             print("Could not parse pager.")
#             return False

#         current = int(match.group(1))
#         total   = int(match.group(2))

#         if current >= total:
#             print(f"No more pages — {current}/{total}.")
#             return False

#         # Click next
#         await page.locator("#divPagerBottom li.next").click()
#         await page.wait_for_selector(
#             "[class*='property-thumbnail-item']",
#             state="detached",
#             timeout=5000
#         )
#         await page.wait_for_selector(
#             "[class*='property-thumbnail-item']",
#             state="attached",
#             timeout=15000
#         )
#         print(f"  → Moved to page {current + 1}/{total}")
#         return True

#     except Exception as e:
#         print(f"Pagination error: {e}")
#         return False

async def extract_broker_url(page: Page) -> dict | None:
    """Extract broker URL and parse basic info from listing detail page."""
    try:
        broker_link = page.locator("a[href*='real-estate-broker'][href*='/d']")
        if await broker_link.count() == 0:
            return None

        href = await broker_link.first.get_attribute("href")
        if not href or "contact" in href or "choose" in href.lower():
            return None

        # Parse info directly from URL
        # Format: /en/real-estate-broker~name~agency/id
        parts   = href.split('/')
        broker_id = parts[-1]  # e.g., 'd6974'
        slug    = parts[-2] if len(parts) > 2 else ""
        slugs   = slug.split('~')

        raw_name   = slugs[1].replace('-', ' ').title() if len(slugs) > 1 else None
        raw_agency = slugs[2].replace('-', ' ').title() if len(slugs) > 2 else None

        return {
            "broker_id":  broker_id,
            "broker_url": f"{BASE_URL}" + href,
            "raw_name":   raw_name,
            "raw_agency": raw_agency,
        }
    except Exception:
        return None


async def extract_broker_details(page: Page, broker_url: str) -> dict:
    """Visit broker profile page and extract full details."""
    await page.goto(broker_url)
    await page.wait_for_load_state("networkidle")
    await human_delay()

    # Phone lives in href="tel:..." attribute
    phone = None
    phone_link = page.locator("a[href*='tel:']")
    if await phone_link.count() > 0:
        raw_phone = await phone_link.first.get_attribute("href")
        phone = raw_phone.replace("tel:", "").strip() if raw_phone else None

    # Contact URL instead of email (email is hidden behind contact form)
    contact_url = None
    contact_link = page.locator("a[href*='contact-broker']")
    if await contact_link.count() > 0:
        href = await contact_link.first.get_attribute("href")
        contact_url = f"{BASE_URL}" + href if href else None

    return {
        "full_name":   await safe_text(page.locator("h1.broker-info__broker-title")),
        "phone":       phone,
        "contact_url": contact_url,
        "agency_name": await safe_text(page.locator("h2.broker-info__agency-name")),
    }


async def extract_financial_details(page: Page) -> dict:
    """Dynamically extract all rows from the financial details tables."""
    result = {
        "lot_assessment":      None,
        "building_assessment": None,
        "municipal_assessment": None,
        "assessment_year":     None,
        "financial_data":      {}  # catches everything dynamically
    }

    try:
        container = page.locator(".financial-details-container")
        if await container.count() == 0:
            return result

        # --- Municipal assessment (always static structure) ---
        assessment_header = container.locator(
            "th.financial-details-table-title"
        ).filter(has_text="Municipal assessment")

        if await assessment_header.count() > 0:
            header_text = await assessment_header.first.text_content()
            year_match  = re.search(r'\((\d{4})\)', header_text) # type: ignore
            if year_match:
                result["assessment_year"] = int(year_match.group(1))

            assessment_table = assessment_header.locator("xpath=../../../..")
            rows  = assessment_table.locator("tbody tr")
            count = await rows.count()

            for i in range(count):
                row   = rows.nth(i)
                label = await row.locator("td:first-child").text_content()
                value = await row.locator("td.text-right").text_content()
                label = label.strip().lower() # type: ignore
                value = parse_float(value)
                if "lot" in label:
                    result["lot_assessment"] = value
                elif "building" in label:
                    result["building_assessment"] = value

            total = assessment_table.locator(
                "tfoot .financial-details-table-total td.text-right"
            )
            if await total.count() > 0:
                result["municipal_assessment"] = parse_float(
                    await total.text_content()
                )

        # --- All yearly tables — fully dynamic ---
        yearly_tables = container.locator(
            ".financial-details-table-yearly table, "
            ".financial-details-table:not(.financial-details-table-monthly) table"
        )
        table_count = await yearly_tables.count()

        for t in range(table_count):
            table = yearly_tables.nth(t)

            # Get table title
            title_el = table.locator("th.financial-details-table-title")
            title = await title_el.text_content() if await title_el.count() > 0 else f"table_{t}"
            title = title.strip().lower().replace(" ", "_") # type: ignore

            # Get all rows dynamically
            rows  = table.locator("tbody tr")
            count = await rows.count()

            for i in range(count):
                row   = rows.nth(i)
                label = await row.locator("td:first-child").text_content()
                value = await row.locator("td.text-right").text_content()

                if not label or not value:
                    continue

                # Clean label into snake_case key
                clean_label = (
                    label.strip()
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("/", "_")
                )
                clean_key = f"{title}__{clean_label}"
                result["financial_data"][clean_key] = parse_float(value)

            # Also grab tfoot total
            total = table.locator(
                "tfoot .financial-details-table-total td.text-right"
            )
            if await total.count() > 0:
                result["financial_data"][f"{title}__total"] = parse_float(
                    await total.text_content()
                )

    except Exception as e:
        print(f"  ⚠️ Financial details error: {e}")

    return result