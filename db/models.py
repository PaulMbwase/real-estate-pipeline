from sqlalchemy import (UniqueConstraint, create_engine, String, Text,
                        Numeric, SmallInteger, Boolean,
                        Date, TIMESTAMP, ForeignKey)
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime, date
from decimal import Decimal
import os

load_dotenv()

DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"client_encoding": "utf8"}
)
Base = declarative_base()


class Broker(Base):
    __tablename__ = "brokers"
    id: Mapped[int] = mapped_column(primary_key=True)
    broker_id: Mapped[str] = mapped_column(String(50), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    contact_url: Mapped[Optional[str]] = mapped_column(Text)
    agency_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

class Location(Base):
    __tablename__ = "locations"
    id:           Mapped[int] = mapped_column(primary_key=True)
    address:      Mapped[Optional[str]] = mapped_column(String(255))
    province:     Mapped[Optional[str]] = mapped_column(String(50))
    postal_code:  Mapped[Optional[str]] = mapped_column(String(10))
    civic_number: Mapped[Optional[str]] = mapped_column(String(20))
    unit_number:  Mapped[Optional[str]] = mapped_column(String(20))
    street_name:  Mapped[Optional[str]] = mapped_column(String(100))
    street_type:  Mapped[Optional[str]] = mapped_column(String(20))
    borough:      Mapped[Optional[str]] = mapped_column(String(100))
    city:         Mapped[Optional[str]] = mapped_column(String(100))
    neighborhood: Mapped[Optional[str]] = mapped_column(String(150))
    latitude:     Mapped[Optional[Decimal]] = mapped_column(Numeric(9,6))
    longitude:    Mapped[Optional[Decimal]] = mapped_column(Numeric(9,6))
    created_at:   Mapped[datetime] = mapped_column(default=datetime.now)


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("locations.id"))
    # property_id: Mapped[str] = mapped_column(String(50), unique=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    year_built: Mapped[Optional[int]] = mapped_column(SmallInteger)
    size_sqft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))
    lot_size_sqft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))
    floors: Mapped[Optional[int]] = mapped_column(SmallInteger)
    total_rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bedrooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bathrooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    half_bathrooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    parking: Mapped[Optional[int]] = mapped_column(SmallInteger)
    garage: Mapped[bool] = mapped_column(Boolean, default=False)
    pool: Mapped[bool] = mapped_column(Boolean, default=False)
    basement: Mapped[bool] = mapped_column(Boolean, default=False)
    waterfront: Mapped[bool] = mapped_column(Boolean, default=False)
    lot_assessment:       Mapped[Optional[Decimal]] = mapped_column(Numeric(12,2))
    building_assessment:  Mapped[Optional[Decimal]] = mapped_column(Numeric(12,2))
    municipal_assessment: Mapped[Optional[Decimal]] = mapped_column(Numeric(12,2))
    assessment_year:      Mapped[Optional[int]] = mapped_column(SmallInteger)
    municipal_taxes:      Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))
    characteristics: Mapped[Optional[dict]] = mapped_column(JSONB)
    school_taxes:         Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2))
    financial_data:       Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (                                          # 👈 add this block
        UniqueConstraint("listing_id", "category", name="listings_listing_id_category_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brokers.id"))
    listing_id: Mapped[str] = mapped_column(String(50))
    category: Mapped[Optional[str]] = mapped_column(String(50))
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12,2))
    status: Mapped[str] = mapped_column(String(20), default="Active")
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    list_date: Mapped[Optional[date]] = mapped_column(Date, default=date.today)
    sold_date: Mapped[Optional[date]] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(12,2))
    recorded_at: Mapped[datetime] = mapped_column(default=datetime.now)


class ListingImage(Base):
    __tablename__ = "listing_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    image_url: Mapped[str] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, default=0)


class ListingCondo(Base):
    __tablename__ = "listing_condo"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), unique=True)
    condo_fees: Mapped[Optional[Decimal]] = mapped_column(Numeric(8,2))
    floor_number: Mapped[Optional[int]] = mapped_column(SmallInteger)
    total_floors: Mapped[Optional[int]] = mapped_column(SmallInteger)
    locker: Mapped[bool] = mapped_column(Boolean, default=False)


class ListingPlex(Base):
    __tablename__ = "listing_plex"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), unique=True)
    units: Mapped[int] = mapped_column(SmallInteger)
    rental_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(12,2))
    kitchens: Mapped[Optional[int]] = mapped_column(SmallInteger)


class ListingCommercial(Base):
    __tablename__ = "listing_commercial"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    zoning: Mapped[Optional[str]] = mapped_column(Text)
    business_type: Mapped[Optional[str]] = mapped_column(Text)
    ceiling_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(8,2))
    rent_per_sqft: Mapped[Optional[Decimal]] = mapped_column(Numeric(8,2))
    rent_period:   Mapped[Optional[str]] = mapped_column(String(20))


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("All tables created successfully!")