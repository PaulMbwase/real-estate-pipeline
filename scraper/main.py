# scraper/main.py
import time
import random
import multiprocessing
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from scraper.scraper import *
from scraper.utils import *
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
TARGET_URL_RESIDENTIAL = os.getenv("TARGET_URL_RESIDENTIAL")
TARGET_URL_COMMERCIAL  = os.getenv("TARGET_URL_COMMERCIAL")

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
            agency_name = safe_truncate(broker_data.get("agency_name"), 255),
        )
        session.add(broker)
        session.flush()  # get broker.id without full commit
        print(f"  New broker: {full_name}")

    return broker


def upsert_location(session: Session, address: str | None, detail: dict) -> Location:
    """Insert location if not exists, return location object."""
    location = session.scalar(
        select(Location).where(Location.address == address)
    )
    if not location:
        location = Location(
            address   = address,
            province  = "QC",
            latitude  = float(detail["latitude"])  if detail.get("latitude")  is not None else None,
            longitude = float(detail["longitude"]) if detail.get("longitude") is not None else None,
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
            property_type  = normalize_property_type(listing_data.get("category")),
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
            characteristics      = detail.get("chars", {}),
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

    if raw_price is not None:
        if isinstance(raw_price, (int, float)):
            price = float(raw_price)
        else:
            # Detect commercial rental pricing — e.g. "$1 /year /square foot"
            raw_str = str(raw_price).lower()
            if "square foot" in raw_str or "/year" in raw_str or "/month" in raw_str:
                commercial_price = parse_commercial_price(raw_price)
                price = commercial_price["price"]
                listing_data["rent_per_sqft"] = commercial_price["rent_per_sqft"]
                listing_data["rent_period"]   = commercial_price["rent_period"]
            else:
                match = re.search(r'[\d,]+', str(raw_price).replace(" ", ""))
                price = float(match.group().replace(",", "")) if match else None

    if not listing:
        listing = Listing(
            property_id = prop.id,
            broker_id   = broker.id if broker else None,
            listing_id  = listing_id,
            category    = listing_data.get("transaction_type"),
            price       = price,
            status      = "Active",
            description = detail.get("description"),
            url         = listing_data.get("property_url"),
        )
        session.add(listing)
        session.flush()
        if price:
            session.add(PriceHistory(
                listing_id = listing.id,
                price      = price,
            ))
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
                              listing_data: dict, detail: dict, prop) -> None:
    """Insert into the appropriate extension table based on property type."""
    # category = (listing_data.get("category") or "").lower()
    category = prop.property_type or ""

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

    elif any(x in category for x in ["commercial", "office", "industrial", 
                            "restaurant", "warehouse", "retail",
                            "business", "building", "income_properties"]):
        existing = session.scalar(
            select(ListingCommercial).where(ListingCommercial.listing_id == listing.id)
        )
        if not existing:
            session.add(ListingCommercial(
                listing_id     = listing.id,
                zoning         = safe_truncate(detail.get("zoning"), 255),
                business_type  = safe_truncate(detail.get("business_type"), 255),
                ceiling_height = parse_float(detail.get("ceiling_height"), max_value=50.0),
                rent_per_sqft = listing_data.get("rent_per_sqft"),
                rent_period   = listing_data.get("rent_period"),
            ))

########################
### MAIN PIPELINE ######
########################
async def main(target_url: str):
    async with async_playwright() as p:

        USER_AGENTS = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ]


        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )
        page = await context.new_page()

        success = await safe_goto(page, f"{BASE_URL}")
        if not success:
            print(f"  ❌ Skipping — could not reach {url}")
            

        await handle_cookies(page)

       

        success = await safe_goto(page, target_url)
        if not success:
            print(f"  ❌ Skipping — could not reach {url}")
            

        total_pages = await get_total_pages(page)
        print(f"Total pages: {total_pages}")

        scraped_brokers = {}

        with Session(engine) as session:
            # Warm up broker cache from DB
            existing_broker_ids = session.scalars(select(Broker.broker_id)).all()
            scraped_brokers     = {bid: None for bid in existing_broker_ids}
            print(f"  Loaded {len(scraped_brokers)} brokers from cache.")

            for page_num in range(1, total_pages + 1):
                await wait_for_network()
                print(f"\n--- Scraping page {page_num}/{total_pages} ---")

                # Recover browser if it died
                try:
                    await page.title()
                except Exception:
                    print("  ⚠️ Browser died — restarting...")
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    browser = await p.chromium.launch(headless=False)
                    page = await browser.new_page()

                    success = await safe_goto(page, f"{BASE_URL}")
                    if not success:
                        print(f"  ❌ Skipping — could not reach {url}")
                        continue
                    
                    await handle_cookies(page)

                try:
                    page_url = f"{target_url}&page={page_num}"

                    success = await safe_goto(page, page_url)
                    if not success:
                        print(f"  ❌ Skipping — could not reach {url}")
                        

                
                except Exception as e:
                    print(f"  ❌ Failed to load page {page_num}: {e}")
                    continue

                listings = await get_listings_from_page(page)

                for listing_data in listings:
                    try:
                        print(f"\nProcessing: {listing_data['property_id']}")
                        url = listing_data.get("property_url")
                        if not url:
                            continue

                        detail = await enrich_listing(page, url)
                        await save_raw(listing_data["property_id"], {**listing_data, **detail})
                        
                        try:
                            # geo = await geocode_address(listing_data.get("address"))
                            # Coordinates from page first, Nominatim only as fallback
                            # Priority: card coords → page meta → Nominatim fallback
                            coords = {
                                "latitude":  listing_data.get("card_latitude")  or detail.get("latitude"),
                                "longitude": listing_data.get("card_longitude") or detail.get("longitude"),
                            }
                            if not coords["latitude"]:
                                coords = await geocode_address(listing_data.get("address"))
                                print(f"  📍 Result: {coords}")

                            detail["latitude"]  = coords["latitude"]
                            detail["longitude"] = coords["longitude"]
                        except Exception:
                            detail = {"latitude": None, "longitude": None} # type: ignore
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

                            # await page.goto(url)
                            # await page.wait_for_load_state("networkidle")

                        with session.begin_nested():
                            location = upsert_location(session, listing_data.get("address"), detail)
                            prop     = upsert_property(session, listing_data, detail, location)
                            if not prop:
                                continue
                            transaction_types = normalize_transaction_type(listing_data.get("category"))

                            for transaction_type in transaction_types:
                                listing_data["transaction_type"] = transaction_type
                                listing = upsert_listing(session, listing_data, detail, prop, broker)
                                if not listing:
                                    continue
                                insert_images(session, listing, detail.get("images", []))
                                insert_listing_extension(session, listing, listing_data, detail, prop)


                        session.commit()
                        print(f"  ✅ Saved: {listing_data['property_id']}")
                        # time.sleep(random.randint(1,3))

                    except Exception as e:
                        print(f"  ❌ Failed: {listing_data['property_id']} — {e}")
                        session.rollback()
                        continue

        await browser.close()
        print("\n✅ Scraping complete.")

##############################
##### MULTIPROCESSING SETUP ##
##############################


def start_scraper(target_url: str):
    """Entry point for each process — each gets its own event loop."""
    asyncio.run(main(target_url))


if __name__ == "__main__":
    start = time.perf_counter()
    p1 = multiprocessing.Process(
        target=start_scraper,
        args=(TARGET_URL_RESIDENTIAL,),
        name="residential"
    )
    p2 = multiprocessing.Process(
        target=start_scraper,
        args=(TARGET_URL_COMMERCIAL,),
        name="commercial"
    )

    p1.start()
    p2.start()
    print("Both scrapers running in parallel...")
    p1.join()
    p2.join()
    print("Both scrapers finished.")
    end = time.perf_counter()
    print(f"Elapsed time: {end - start:.6f} seconds")
