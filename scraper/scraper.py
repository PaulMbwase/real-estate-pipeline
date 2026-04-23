# scraper/scraper.py

import json
from datetime import datetime 
from playwright.async_api import Page
from scraper.utils import safe_text, safe_attr, clean_address, extract_detail
from dotenv import load_dotenv
import os
import re

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


async def get_listings_from_page(page: Page) -> list[dict]:
    """Extract all listing cards from a search results page."""
    try:
        await page.wait_for_selector(
            "[class*='property-thumbnail-item']",
            timeout=10000  # shorter timeout
        )
    except Exception:
        print("  ⚠️ No listings found on this page — skipping.")
        return []

    cards = page.locator("[class*='property-thumbnail-item']")
    count = await cards.count()
    print(f"Listings found on page: {count}")

    listings = []
    for i in range(count):
        card = cards.nth(i)
        raw_address  = await safe_text(card.locator("[class*='address']"))
        address      = await clean_address(raw_address)
        price        = await safe_text(card.locator("[class*='price']"))
        property_url = await safe_attr(card.locator("a"), "href")
        property_id  = property_url.split('/')[-1] if property_url else None

        listings.append({
            "property_id":  property_id,
            "category":     await safe_text(card.locator("[class*='category']")),
            "price":        price if price and "$" in price else None,
            "address":      address,
            "bedrooms":     await safe_text(card.locator("[class*='cac']")),
            "bathrooms":    await safe_text(card.locator("[class*='sdb']")),
            "property_url": f"{BASE_URL}" + property_url if property_url else None
        })

    return listings


async def enrich_listing(page: Page, url: str) -> dict:
    """Visit a listing detail page and extract deep features."""
    await page.goto(url)
    await page.wait_for_load_state("networkidle")

    return {
        "size_sqft":    await extract_detail(page, "Superficie habitable", "Living area"),
        "year_built":   await extract_detail(page, "Année de construction", "Year built"),
        "broker":       await extract_detail(page, "Courtier", "Real estate broker"),
        "total_rooms":  await extract_detail(page, "Pièces", "Rooms"),
        "garage":       await extract_detail(page, "Garage", "Garage"),
        "pool":         await extract_detail(page, "Piscine", "Pool"),
        "lot_size":     await extract_detail(page, "Superficie du terrain", "Lot area"),
        "floors":       await extract_detail(page, "Étages", "Floors"),
        "description":  await safe_text(page.locator("[itemprop='description']")),
        "images":       await get_images(page),
    }


async def save_raw(property_id: str, data: dict) -> None:
    """Save raw scraped data to data/raw/ as JSON."""
    os.makedirs("data/raw", exist_ok=True)
    filepath = f"data/raw/{property_id}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

async def get_images(page: Page) -> list[str]:
    """Extract all image URLs from a listing detail page."""
    try:
        images = page.locator("img[class*='thumbnail'], img[class*='photo']")
        count  = await images.count()
        urls   = []
        for i in range(count):
            src = await images.nth(i).get_attribute("src")
            if src:
                urls.append(src)
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
        if not href:
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