# scraper/main.py
import time
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from scraper.scraper import (
    handle_cookies,
    get_listings_from_page,
    enrich_listing,
    extract_broker_url,
    extract_broker_details,
    save_raw,
    get_total_pages
)
from scraper.utils import geocode_address
from scraper.parse_helpers import *
from db.models import (
    engine, Base,
    Broker, Location, Property,
    Listing, ListingImage,
    ListingCondo, ListingPlex, ListingCommercial,
    PriceHistory
)
from sqlalchemy.orm import Session
from sqlalchemy import select
import os

load_dotenv()

BASE_URL  = os.getenv("BASE_URL")
TARGET_URL = os.getenv("TARGET_URL")


# ----------------------------
# DB INSERTION HELPERS
# ----------------------------

def upsert_broker(session: Session, broker_data: dict) -> Broker | None:
    """Insert broker if not exists, return broker object."""
    if not broker_data or not broker_data.get("broker_id"):
        return None

    broker = session.scalar(
        select(Broker).where(Broker.broker_id == broker_data["broker_id"])
    )

    if not broker:
        # Split full name into first and last
        full_name  = broker_data.get("full_name") or ""
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else None
        last_name  = name_parts[1] if len(name_parts) > 1 else None

        broker = Broker(
            broker_id   = broker_data["broker_id"],
            first_name  = first_name or "Unknown",
            last_name   = last_name  or "Unknown",
            phone       = broker_data.get("phone"),
            contact_url = broker_data.get("contact_url"),
            agency_name = broker_data.get("agency_name"),
        )
        session.add(broker)
        session.flush()  # get broker.id without full commit
        print(f"  New broker: {full_name}")

    return broker


def upsert_location(session: Session, address: str | None, geo: dict) -> Location:
    location = session.scalar(
        select(Location).where(Location.address == address)
    )
    if not location:
        location = Location(
            address   = address,
            province  = "QC",
            latitude  = geo.get("latitude"),
            longitude = geo.get("longitude"),
        )
        session.add(location)
        session.flush()
    return location

# def upsert_location(session: Session, listing_data: dict, geo: dict) -> Location:
#     """Insert location if not exists, return location object."""
#     street = listing_data.get("street")
#     city   = listing_data.get("city")

#     location = session.scalar(
#         select(Location).where(
#             Location.street_address == street,
#             Location.city == city
#         )
#     )

#     if not location:
#         location = Location(
#             street_address = street,
#             city           = city,
#             province       = "QC",
#             latitude       = geo.get("latitude"),
#             longitude      = geo.get("longitude"),
#         )
#         session.add(location)
#         session.flush()

#     return location

def upsert_property(session: Session, listing_data: dict,
                    detail: dict, location: Location) -> Property | None:
    property_id = listing_data.get("property_id")
    if not property_id:
        return None

    prop = session.scalar(
        select(Property).where(Property.property_id == property_id)
    )

    if not prop:
        prop = Property(
            location_id    = location.id,
            property_id    = property_id,
            property_type  = listing_data.get("category"),
            year_built     = parse_year(detail.get("year_built")),
            size_sqft      = parse_float(detail.get("size_sqft")),
            lot_size_sqft  = parse_float(detail.get("lot_size")),
            floors         = parse_int(detail.get("floors")),
            total_rooms    = parse_int(detail.get("total_rooms")),
            bedrooms       = parse_int(listing_data.get("bedrooms")),
            bathrooms      = parse_int(listing_data.get("bathrooms")),
            half_bathrooms = parse_int(detail.get("half_bathrooms")),
            parking        = parse_int(detail.get("parking")),
            garage         = parse_bool(detail.get("garage")),
            pool           = parse_bool(detail.get("pool")),
            basement       = parse_bool(detail.get("basement")),
            waterfront     = False,
            lot_assessment       = parse_float(detail.get("lot_assessment")),
            building_assessment  = parse_float(detail.get("building_assessment")),
            municipal_assessment = parse_float(detail.get("municipal_assessment")),
            assessment_year      = parse_int(detail.get("assessment_year")),
            municipal_taxes      = parse_float(detail.get("municipal_taxes")),
            school_taxes         = parse_float(detail.get("school_taxes")),
            financial_data       = detail.get("financial_data", {}),
        )
        session.add(prop)
        session.flush()

    return prop

def upsert_listing(session: Session, listing_data: dict,
                   detail: dict, prop: Property, 
                   broker: Broker | None) -> Listing | None:
    """Insert or update listing, track price history."""
    listing_id = listing_data.get("property_id")
    if not listing_id:
        return None

    listing = session.scalar(
        select(Listing).where(Listing.listing_id == listing_id)
    )

    raw_price = listing_data.get("price")
    price     = None
    if raw_price:
        # Clean price string → Decimal : "$450,000" → 450000.00
        # price = raw_price.replace("$", "").replace(",", "").replace(" ", "").strip()
        match = re.search(r'[\d,]+', raw_price.replace(" ", ""))
        try:
            price = float(match.group().replace(",", ".")) if match else None

        except ValueError:
            price = None

    if not listing:
        listing = Listing(
            property_id = prop.id,
            broker_id   = broker.id if broker else None,
            listing_id  = listing_id,
            category    = listing_data.get("category"),
            price       = price,
            status      = "Active",
            description = detail.get("description"),
            url         = listing_data.get("property_url"),
        )
        session.add(listing)
        session.flush()
        print(f"  New listing: {listing_id}")

    else:
        # Listing exists — check for price change
        if price and float(listing.price) != float(price): # type: ignore
            print(f"  Price change detected: {listing.price} → {price}")
            history = PriceHistory(
                listing_id  = listing.id,
                price       = listing.price,  # save OLD price
            )
            session.add(history)
            listing.price = price  # type: ignore # update to NEW price

    return listing


def insert_images(session: Session, listing: Listing, images: list[str]) -> None:
    """Insert listing images if not already stored."""
    existing = session.scalar(
        select(ListingImage).where(ListingImage.listing_id == listing.id) # type: ignore
    )
    if existing:
        return  # images already stored

    for i, url in enumerate(images):
        session.add(ListingImage(
            listing_id    = listing.id,
            image_url     = url,
            is_primary    = (i == 0),
            display_order = i
        ))

def insert_listing_extension(session: Session, listing: Listing, 
                              listing_data: dict, detail: dict) -> None:
    """Insert into the appropriate extension table based on property type."""
    category = (listing_data.get("category") or "").lower()

    if "condo" in category:
        existing = session.scalar(
            select(ListingCondo).where(ListingCondo.listing_id == listing.id)
        )
        if not existing:
            session.add(ListingCondo(
                listing_id   = listing.id,
                condo_fees   = parse_float(detail.get("condo_fees")),
                floor_number = parse_int(detail.get("floor_number")),
                total_floors = parse_int(detail.get("total_floors")),
                locker       = parse_bool(detail.get("locker")),
            ))

    elif any(x in category for x in ["plex", "duplex", "triplex", 
                                      "quadruplex", "quintuplex"]):
        existing = session.scalar(
            select(ListingPlex).where(ListingPlex.listing_id == listing.id)
        )
        if not existing:
            session.add(ListingPlex(
                listing_id     = listing.id,
                units          = parse_int(detail.get("units")) or 2,
                rental_income  = parse_float(detail.get("rental_income")),
                kitchens       = parse_int(detail.get("kitchens")),
            ))

    elif "commercial" in category:
        existing = session.scalar(
            select(ListingCommercial).where(ListingCommercial.listing_id == listing.id)
        )
        if not existing:
            session.add(ListingCommercial(
                listing_id     = listing.id,
                zoning         = detail.get("zoning"),
                business_type  = detail.get("business_type"),
                ceiling_height = parse_float(detail.get("ceiling_height")),
            ))
# ----------------------------
# MAIN PIPELINE
# ----------------------------

# async def main():
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=False)
#         page    = await browser.new_page()

#         # Step 1 — Load site and handle cookies
#         await page.goto(f"{BASE_URL}")
#         await page.wait_for_load_state("networkidle")
#         await handle_cookies(page)

#         # Step 2 — Navigate to listings
#         await page.goto(f"{TARGET_URL}")
#         pager = page.locator("#divPagerBottom li.pager-current")
#         print(f"[DEBUG] Pager count: {await pager.count()}")
#         print(f"[DEBUG] Pager text: {await pager.text_content()}")

#         await page.wait_for_load_state("networkidle")

#         scraped_brokers = {}  # broker_id → Broker object cache
#         page_num        = 1

#         with Session(engine) as session:
#             while True:
#                 print(f"\n--- Scraping page {page_num} ---")

#                 # Phase 1 — Extract listing cards
#                 listings = await get_listings_from_page(page)

#                 for listing_data in listings:
#                     print(f"\nProcessing: {listing_data['property_id']}")
#                     url = listing_data.get("property_url")
#                     if not url:
#                         continue

#                     # Phase 2 — Enrich from detail page
#                     detail = await enrich_listing(page, url)
#                     await save_raw(listing_data["property_id"], {**listing_data, **detail})

#                     # Geocode address
#                     geo = await geocode_address(
#                         listing_data.get("street"),
#                         listing_data.get("city")
#                     )

#                     # Extract broker
#                     broker_info = await extract_broker_url(page)
#                     broker      = None

#                     if broker_info:
#                         broker_id = broker_info["broker_id"]

#                         if broker_id not in scraped_brokers:
#                             # Visit broker page only once
#                             broker_details = await extract_broker_details(
#                                 page, broker_info["broker_url"]
#                             )
#                             broker_info.update(broker_details)

#                             with session.begin_nested():
#                                 broker = upsert_broker(session, broker_info)
#                             scraped_brokers[broker_id] = broker
#                         else:
#                             broker = scraped_brokers[broker_id]

#                         # Return to listing detail page after broker visit
#                         await page.goto(url)
#                         await page.wait_for_load_state("networkidle")

#                     # Insert into DB
#                     with session.begin_nested():
#                         location = upsert_location(session, listing_data, geo)
#                         prop     = upsert_property(session, listing_data, detail, location)
#                         if not prop:
#                             continue
#                         listing  = upsert_listing(session, listing_data, detail, prop, broker)
#                         if not listing:
#                             continue
#                         insert_images(session, listing, detail.get("images", []))

#                     session.commit()
#                     print(f"  ✅ Saved: {listing_data['property_id']}")

#                 # Pagination
#                 has_next = await paginate(page)
#                 if not has_next:
#                     break
#                 page_num += 1
#                 time.sleep(6000)

#         await browser.close()
#         print("\n✅ Scraping complete.")

# asyncio.run(main())


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page    = await browser.new_page()

        # Step 1 — Load site and handle cookies
        await page.goto(f"{BASE_URL}")
        await page.wait_for_load_state("networkidle")
        await handle_cookies(page)

        # Step 2 — Navigate to listings page 1
        await page.goto(f"{TARGET_URL}")
        await page.wait_for_load_state("networkidle")

        # Step 3 — Get total pages
        total_pages = await get_total_pages(page)
        print(f"Total pages: {total_pages}")

        scraped_brokers = {}

        with Session(engine) as session:
            for page_num in range(1, total_pages + 1):
                print(f"\n--- Scraping page {page_num}/{total_pages} ---")

                # Build page URL directly
                page_url = f"{TARGET_URL}&page={page_num}"
                await page.goto(page_url)
                await page.wait_for_load_state("networkidle")

                listings = await get_listings_from_page(page)

                for listing_data in listings:
                    try:
                        print(f"\nProcessing: {listing_data['property_id']}")
                        url = listing_data.get("property_url")
                        if not url:
                            continue

                        detail = await enrich_listing(page, url)
                        await save_raw(listing_data["property_id"], {**listing_data, **detail})
                        
                        geo = await geocode_address(listing_data.get("address")) # type: ignore
                        # geo = await geocode_address(
                            # listing_data.get("street"),
                            # listing_data.get("city")
                        # )

                        broker_info = await extract_broker_url(page)
                        broker      = None

                        if broker_info:
                            broker_id = broker_info["broker_id"]
                            if broker_id not in scraped_brokers:
                                broker_details = await extract_broker_details(
                                    page, broker_info["broker_url"]
                                )
                                broker_info.update(broker_details)
                                with session.begin_nested():
                                    broker = upsert_broker(session, broker_info)
                                scraped_brokers[broker_id] = broker
                            else:
                                broker = scraped_brokers[broker_id]

                            await page.goto(url)
                            await page.wait_for_load_state("networkidle")

                        with session.begin_nested():
                            location = upsert_location(session, listing_data.get("address"), geo)
                            prop     = upsert_property(session, listing_data, detail, location)
                            if not prop:
                                continue
                            listing  = upsert_listing(session, listing_data, detail, prop, broker)
                            if not listing:
                                continue
                            insert_images(session, listing, detail.get("images", []))
                            insert_listing_extension(session, listing, listing_data, detail)  # ← add this


                        session.commit()
                        print(f"  ✅ Saved: {listing_data['property_id']}")

                    except Exception as e:
                        print(f"  ❌ Failed: {listing_data['property_id']} — {e}")
                        session.rollback()
                        continue

        await browser.close()
        print("\n✅ Scraping complete.")

asyncio.run(main())