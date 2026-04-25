import re
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, update
from db.models import engine, Location
from sqlalchemy.orm import Session
from scraper.parse_helpers import parse_address

def backfill_locations():
    with Session(engine) as session:
        locations = session.scalars(select(Location)).all()
        print(f"Backfilling {len(locations)} locations...")

        updated = 0
        failed  = 0

        for loc in locations:
            try:
                parsed = parse_address(loc.address)

                session.execute(
                    update(Location)
                    .where(Location.id == loc.id)
                    .values(
                        civic_number = parsed.get("civic_number"),
                        unit_number  = parsed.get("unit_number"),
                        street_name  = parsed.get("street_name"),
                        street_type  = parsed.get("street_type"),
                        borough      = parsed.get("borough"),
                        city         = parsed.get("city"),
                    )
                )
                updated += 1

            except Exception as e:
                print(f"  ❌ Failed location {loc.id} — {loc.address} — {e}")
                failed += 1

        session.commit()
        print(f"  ✅ Updated: {updated}")
        print(f"  ❌ Failed:  {failed}")

if __name__ == "__main__":
    backfill_locations()