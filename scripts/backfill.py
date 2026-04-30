# scraper/backfill.py

import asyncio
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from db.models import engine, Property, Location, Listing
from scraper.scraper import extract_financial_details, safe_goto, handle_cookies
from scraper.parse_helpers import parse_float, parse_int
from scraper.parse_helpers import parse_address
from dotenv import load_dotenv
import os

load_dotenv()
BASE_URL = os.getenv("BASE_URL")


def get_listings_to_backfill(session: Session) -> list[dict]:
    """Query listings with missing high-value fields."""
    results = session.execute(
        select(
            Listing.id,
            Listing.url,
            Listing.price,
            Property.id.label("property_id"),
            Property.municipal_taxes,
            Property.building_assessment,
            Property.year_built,
            Property.area_sqft,
            Location.id.label("location_id"),
            Location.borough,
        )
        .join(Property, Listing.property_id == Property.id)
        .join(Location, Property.location_id == Location.id)
        .where(
            or_(
                Property.municipal_taxes    == None,
                Property.building_assessment == None,
                Property.lot_assessment     == None,
                Location.borough            == None,
                Listing.price                   == None,
                Property.area_sqft                == None,
                Property.year_built               == None,
            )
        )
    ).all()

    return [row._asdict() for row in results]


async def backfill_listing(page, listing: dict, session: Session) -> None:
    """Re-visit a listing detail page and fill missing fields."""
    url = listing.get("url")
    if not url:
        return

    success = await safe_goto(page, url)
    if not success:
        print(f"  ❌ Could not reach {url}")
        return

    prop     = session.get(Property, listing["property_id"])
    location = session.get(Location, listing["location_id"])
    price = session.get(Listing, listing["id"]).price

    if not prop or not location:
        return

    # Backfill financial data
    if prop.municipal_taxes is None or prop.building_assessment is None:
        financial = await extract_financial_details(page)

        if prop.lot_assessment is None:
            prop.lot_assessment = parse_float(str(financial.get("lot_assessment")))
        if prop.building_assessment is None:
            prop.building_assessment = parse_float(str(financial.get("building_assessment")))
        if prop.municipal_assessment is None:
            prop.municipal_assessment = parse_float(str(financial.get("municipal_assessment")))
        if prop.assessment_year is None:
            prop.assessment_year = parse_int(str(financial.get("assessment_year")))
        if prop.municipal_taxes is None:
            prop.municipal_taxes = financial.get("municipal_taxes")
        if prop.school_taxes is None:
            prop.school_taxes = financial.get("school_taxes")

    # Backfill borough from address meta
    if location.borough is None:
        try:
            raw = await page.locator(
                "meta[itemprop='address']"
            ).get_attribute("content")
            if raw:
                components = parse_address(raw)
                if components.get("borough"):
                    location.borough = components["borough"]
        except Exception:
            pass

    # Backfill price if missing
    if price is None:
        try:
            price_str = await page.locator("span[itemprop='price']").inner_text()
            price = parse_float(price_str)
            if price:
                session.execute(
                    select(Listing).where(Listing.id == listing["id"])
                ).scalar_one().price = price
        except Exception:
            pass

    session.commit()
    print(f"  ✅ Backfilled: {url.split('/')[-1]}")


async def main():
    with Session(engine) as session:
        listings = get_listings_to_backfill(session)
        print(f"Found {len(listings)} listings to backfill.")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page    = await browser.new_page()

            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")
            await handle_cookies(page)

            for i, listing in enumerate(listings):
                try:
                    print(f"\n[{i+1}/{len(listings)}] Processing: {listing['url']}")
                    await backfill_listing(page, listing, session)
                    await asyncio.sleep(1.5)  # respectful delay
                except Exception as e:
                    print(f"  ❌ Failed: {e}")
                    continue

            await browser.close()

    print("\n✅ Backfill complete.")

asyncio.run(main())