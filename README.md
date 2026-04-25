# Real Estate Pipeline

An end-to-end data engineering and machine learning pipeline for real estate market analysis. This project scrapes property listings, stores them in a normalized PostgreSQL database, and will power price prediction models and a REST API.

> ⚠️ The data source URL is intentionally omitted from this repository and stored in `.env` to avoid search engine indexing.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Project Structure](#project-structure)
- [Step 1 — Database Design](#step-1--database-design)
- [Step 2 — Scraping Pipeline](#step-2--scraping-pipeline)
- [Step 3 — Data Analysis & Price Prediction](#step-3--data-analysis--price-prediction) *(coming soon)*
- [Step 4 — API](#step-4--api) *(coming soon)*
- [Setup & Installation](#setup--installation)

---

## Project Overview

This project is structured as a four-step pipeline:

```
Scraping (Playwright)
    ↓
PostgreSQL Database (SQLAlchemy)
    ↓
Data Analysis & ML (Jupyter / Scikit-learn)
    ↓
REST API (FastAPI)
```

**Target data:** Residential and commercial property listings across Quebec, Canada — starting with the Montreal metropolitan area and expanding city by city. The architecture is designed for province-wide coverage and repeated scraping runs to achieve dataset completeness.

**Key features:**
- Dynamic scraping of JavaScript-rendered pages using Playwright
- Normalized relational schema with 9 tables
- Structured address parsing with normalization (street type, borough, city)
- Dual listing support — same property listed simultaneously for sale and for rent
- Price history tracking across scraping runs
- Freshness tracking via `updated_at` — detects delisted properties over time
- Geolocation via embedded page metadata with Nominatim fallback
- Dynamic financial data extraction stored as JSONB
- Anti-scraping protections: random delays, user agent rotation, retry logic
- Parallel scraping of residential and commercial listings via multiprocessing
- Multi-city scraping strategy with incremental dataset growth

---

## Project Structure

```
real-estate-pipeline/
├── db/
│   ├── schema.sql              # Raw SQL schema (reference)
│   ├── queries.sql             # Raw SQL queries for DB inspection
│   └── models.py               # SQLAlchemy ORM models (source of truth)
├── scraper/
│   ├── __init__.py
│   ├── main.py                 # Pipeline orchestration + DB insertion
│   ├── scraper.py              # Playwright scraping functions
│   ├── utils.py                # Helper functions (safe_text, geocoding)
│   └── parse_helpers.py        # Data cleaning, type parsing, normalization
├── scripts/
│   └── backfill_locations.py   # One-shot backfill for address normalization
├── analysis/
│   └── notebooks/              # Jupyter notebooks for EDA and ML
├── api/
│   └── main.py                 # FastAPI application (coming soon)
├── data/
│   ├── raw/                    # Raw JSON snapshots per listing (gitignored)
│   ├── processed/              # Cleaned data ready for ML (gitignored)
│   └── exports/                # Database backups and CSV exports (gitignored)
├── .env                        # Credentials and target URLs (never committed)
├── .gitignore
├── .gitattributes
├── requirements.txt
└── README.md
```

---

## Step 1 — Database Design

### Design Philosophy

The schema follows **3rd Normal Form (3NF)** to eliminate data redundancy. The core principle is that information is stored exactly once and referenced by foreign keys everywhere else.

Three key distinctions drive the schema:

**Property vs Listing** — A `property` is the physical asset (the building or land). A `listing` is the commercial offer (the act of putting it on the market). One property can have multiple listings over time — re-listed after expiry, or simultaneously offered for sale and for rent.

**Platform ID vs Internal ID** — The Centris platform ID is stored once, in `listings.listing_id`, where it belongs. The `properties` table uses its own internal primary key, decoupled from any external platform. This prevents tight coupling to a single data source.

**Structured address** — Addresses are parsed into normalized components (civic number, street name, street type, borough, city) enabling reliable deduplication, geocoding, and cross-city comparison without false matches from abbreviation variants like "Rue" vs "Rue" or "Ave" vs "Avenue".

### Schema Map

```
locations
    ↑
properties ──────────────→ locations
    ↑
listings ────────────────→ properties
         ↘               → brokers
          ↓
    price_history         (one per price change)
    listing_images        (many per listing)
    listing_condo         (one-to-one extension)
    listing_plex          (one-to-one extension)
    listing_commercial    (one-to-one extension)
```

### Table Reference

#### `brokers`
Stores real estate broker information, deduplicated across listings.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `broker_id` | VARCHAR | Source platform broker ID |
| `first_name` | VARCHAR(100) | Broker first name |
| `last_name` | VARCHAR(100) | Broker last name |
| `phone` | VARCHAR(20) | Contact phone |
| `contact_url` | TEXT | Broker contact page URL |
| `agency_name` | VARCHAR(255) | Real estate agency |
| `created_at` | TIMESTAMP | Record insertion time |

> `broker_id` is nullable — some listings are posted directly by the platform without a broker.

---

#### `locations`
Stores geographic information with fully normalized address components. Shared across multiple properties at the same address.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `address` | TEXT | Raw full civic address (preserved for geocoding fallback) |
| `civic_number` | VARCHAR(20) | Civic number or range (e.g. "353", "353-355", "9635B") |
| `unit_number` | VARCHAR(20) | Apartment or unit number (e.g. "304", "suite 119") |
| `street_name` | VARCHAR(100) | Normalized street name (e.g. "saint-jacques") |
| `street_type` | VARCHAR(20) | Normalized street type (e.g. "rue", "avenue", "boulevard") |
| `borough` | VARCHAR(100) | Borough within city (e.g. "Ville-Marie", "Outremont") |
| `city` | VARCHAR(100) | Municipality (e.g. "Montréal", "Laval") |
| `postal_code` | VARCHAR(10) | Postal code |
| `province` | VARCHAR(50) | Province code (QC) |
| `latitude` | DECIMAL(9,6) | GPS latitude |
| `longitude` | DECIMAL(9,6) | GPS longitude |

> **Address normalization** — Street types are normalized to a canonical form ("St" → "rue", "Ave" → "avenue", "Blvd" → "boulevard") and street names resolve common abbreviations ("St-Jacques" → "saint-jacques"). Deduplication uses the composite key `civic_number + unit_number + street_name + street_type + city`, with NULL-safe matching via COALESCE.

> **Coordinates** — Extracted first from schema.org `<meta itemprop>` tags on the listing card, then from the detail page metadata. A Nominatim (OpenStreetMap) geocoding fallback is used when metadata is absent, using the cleaned address without unit numbers or lot identifiers to maximize match accuracy.

---

#### `properties`
Represents the physical asset — the building or land itself, independent of any listing offer. Identified by its location, not by any platform ID.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `location_id` | INT FK | Reference to `locations` |
| `property_type` | VARCHAR(50) | Normalized type (condo, house, duplex, triplex, commercial, etc.) |
| `year_built` | SMALLINT | Construction year |
| `size_sqft` | DECIMAL(10,2) | Living area in square feet |
| `lot_size_sqft` | DECIMAL(10,2) | Lot area in square feet |
| `floors` | SMALLINT | Number of floors |
| `total_rooms` | SMALLINT | Total room count |
| `bedrooms` | SMALLINT | Bedroom count |
| `bathrooms` | SMALLINT | Bathroom count |
| `half_bathrooms` | SMALLINT | Powder room count |
| `parking` | SMALLINT | Number of parking spots |
| `garage` | BOOLEAN | Garage present |
| `pool` | BOOLEAN | Pool present |
| `basement` | BOOLEAN | Basement present |
| `waterfront` | BOOLEAN | Waterfront property |
| `lot_assessment` | DECIMAL(12,2) | Municipal lot assessment value |
| `building_assessment` | DECIMAL(12,2) | Municipal building assessment value |
| `municipal_assessment` | DECIMAL(12,2) | Total municipal assessment |
| `assessment_year` | SMALLINT | Year of assessment |
| `municipal_taxes` | DECIMAL(10,2) | Annual municipal taxes |
| `school_taxes` | DECIMAL(10,2) | Annual school taxes |
| `financial_data` | JSONB | Dynamic financial rows (varies by property type) |
| `characteristics` | JSONB | All key-value pairs from listing characteristics section |
| `created_at` | TIMESTAMP | Record insertion time |

> The platform ID (Centris listing number) is intentionally not stored here. It belongs to the listing, not the physical asset. A property identified by its normalized location is decoupled from any external platform.

> `financial_data` and `characteristics` use PostgreSQL's JSONB type to store dynamic, property-type-specific data without schema migrations. Both columns are fully queryable and indexable.

---

#### `listings`
Represents the commercial offer — the act of putting a property on the market. One property can have multiple active listings (e.g. simultaneously for sale and for rent).

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `property_id` | INT FK | Reference to `properties` |
| `broker_id` | INT FK | Reference to `brokers` (nullable) |
| `listing_id` | VARCHAR(50) | Centris platform listing ID (single source of truth) |
| `category` | VARCHAR(50) | Transaction type: `for_sale` or `for_rent` |
| `price` | DECIMAL(12,2) | Asking price |
| `status` | VARCHAR(20) | Active, Sold, Expired |
| `description` | TEXT | Marketing description |
| `url` | TEXT | Source listing URL |
| `list_date` | DATE | Date first listed |
| `sold_date` | DATE | Date sold (if applicable) |
| `updated_at` | TIMESTAMP | Last time this listing was seen by the scraper |
| `created_at` | TIMESTAMP | Record insertion time |

> **Dual listing support** — Properties listed simultaneously for sale and for rent are stored as two separate rows, differentiated by the composite unique key `(listing_id, category)`. Price history is tracked independently per row.

> **Freshness tracking** — `updated_at` is refreshed every time the scraper encounters an existing listing. Listings not updated in 30+ days are candidates for delisting detection.

> **Commercial rental pricing** — Commercial listings priced per square foot per year (e.g. "$14.50 /sqft /year") are detected and parsed separately, with `rent_per_sqft` and `rent_period` stored in `listing_commercial`.

---

#### `price_history`
Tracks every price change on a listing over time. The first entry is inserted when the listing is first scraped, establishing a baseline.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `listing_id` | INT FK | Reference to `listings` |
| `price` | DECIMAL(12,2) | Price at this point in time |
| `recorded_at` | TIMESTAMP | When this price was recorded |

---

#### `listing_images`
Stores all image URLs for a listing. Images are never stored in the database — only their URLs.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `listing_id` | INT FK | Reference to `listings` |
| `image_url` | TEXT | Full image URL |
| `is_primary` | BOOLEAN | Cover photo flag |
| `display_order` | SMALLINT | Photo sequence order |

---

#### `listing_condo`
Extension table for condo-specific attributes. One-to-one with `listings`.

| Column | Type | Description |
|--------|------|-------------|
| `listing_id` | INT FK UNIQUE | Reference to `listings` |
| `condo_fees` | DECIMAL(8,2) | Monthly co-ownership fees |
| `floor_number` | SMALLINT | Unit floor number |
| `total_floors` | SMALLINT | Total floors in building |
| `locker` | BOOLEAN | Storage locker included |

---

#### `listing_plex`
Extension table for multi-unit residential properties. One-to-one with `listings`.

| Column | Type | Description |
|--------|------|-------------|
| `listing_id` | INT FK UNIQUE | Reference to `listings` |
| `units` | SMALLINT | Number of residential units |
| `rental_income` | DECIMAL(12,2) | Gross annual rental income |
| `kitchens` | SMALLINT | Number of kitchens |

---

#### `listing_commercial`
Extension table for commercial properties. One-to-one with `listings`.

| Column | Type | Description |
|--------|------|-------------|
| `listing_id` | INT FK UNIQUE | Reference to `listings` |
| `zoning` | TEXT | Zoning classification |
| `business_type` | TEXT | Type of business |
| `ceiling_height` | DECIMAL(8,2) | Ceiling height in feet |
| `rent_per_sqft` | DECIMAL(8,2) | Annual rent per square foot (commercial rentals) |
| `rent_period` | VARCHAR(20) | Rental period: `yearly` or `monthly` |

---

### Key Design Decisions

**Platform ID belongs to the listing, not the property** — The Centris ID is stored once in `listings.listing_id`. The `properties` table is identified by its normalized location, making the schema independent of any single data source and ready for future integration of additional platforms.

**Base + extension model** — Shared fields live in `properties` and type-specific fields extend it via `listing_condo`, `listing_plex`, and `listing_commercial`. This avoids duplicating 15+ columns across tables and allows cross-type queries with a single JOIN.

**Separation of property and listing** — A property that was listed, withdrawn, and re-listed at a different price generates multiple listing rows referencing the same property row. A property simultaneously for sale and for rent generates two listing rows with different `category` values.

**Normalized address components** — Storing raw address strings causes deduplication failures on abbreviation variants and makes geocoding unreliable. Parsing into structured components enables reliable matching, cleaner geocoding queries, and borough-level geographic analysis.

**JSONB for dynamic data** — Financial details and property characteristics vary significantly by listing type and change as the platform evolves. Storing them as JSONB avoids schema migrations while remaining fully queryable in PostgreSQL.

**Price history as time-series** — Every price change is appended rather than overwritten. Combined with `updated_at` freshness tracking, this enables market movement analysis and delisting detection — both strong ML features.

---

## Step 2 — Scraping Pipeline

### Architecture

The scraper is split across four files with clear responsibilities:

```
scraper/main.py          → Orchestration, DB insertion, pipeline loop
scraper/scraper.py       → Playwright page interactions
scraper/utils.py         → Safe extraction helpers, geocoding
scraper/parse_helpers.py → Data cleaning, type casting, normalization
scripts/backfill_*.py    → One-shot data migration and backfill scripts
```

### Two-Phase Scraping Strategy

**Phase 1 — Search results pages**

Each search results page yields up to 20 listing cards. For each card, the scraper extracts:
- Listing URL and platform ID
- Category (property type + transaction type)
- Price (including commercial per-sqft rental pricing)
- Full address
- Bedroom and bathroom counts
- GPS coordinates from `data-lat` / `data-lng` card attributes (when available)

**Phase 2 — Listing detail pages**

Each listing URL is visited individually to extract deeper features:
- GPS coordinates from `<meta itemprop="latitude/longitude">` schema.org tags (fallback from Phase 1)
- All characteristics dynamically from `.carac-container` elements → stored as JSONB
- Financial details (municipal assessment, taxes) from the financial details table → stored as JSONB
- Broker profile URL
- Property images from `data-photo-urls` attribute
- Marketing description

### Parallel Processing

Residential and commercial listings are scraped simultaneously using Python's `multiprocessing` module. Each process runs its own independent browser instance and event loop, writing to the same PostgreSQL database via upsert operations that prevent conflicts.

```python
p1 = multiprocessing.Process(target=start_scraper, args=(TARGET_URL_RESIDENTIAL,))
p2 = multiprocessing.Process(target=start_scraper, args=(TARGET_URL_COMMERCIAL,))
```

### Multi-City Strategy

The platform does not expose all listings in a single paginated run — results are partially randomized per session. The scraping strategy accounts for this:

- Each city is scraped repeatedly until new listings per run drops near zero (saturation)
- Cities are scraped one at a time by updating `.env` target URLs
- The upsert logic makes every run safely additive — no truncation required between runs
- `created_at` and `updated_at` provide a full audit trail of when each listing was first seen and last encountered

Planned city coverage: Montreal Island → Laval → Quebec City → Longueuil → Gatineau → Sherbrooke → South Shore → North Shore.

### Anti-Scraping Protections

| Protection | Implementation |
|-----------|----------------|
| Random delays | `asyncio.sleep(random.uniform(1.5, 4.0))` between listings |
| User agent rotation | Random selection from a pool of real browser user agents |
| Network retry | `safe_goto()` retries failed navigation up to 3 times with exponential backoff |
| Network check | `wait_for_network()` detects connectivity loss at the start of each page |
| Broker deduplication | Broker pages are visited at most once per run via an in-memory cache warmed from DB at startup |
| Block detection | Captcha and block page detection with automatic pause and retry |

### Data Insertion Strategy

All insertions use **upsert logic** — check if the record exists before inserting. Records are deduplicated as follows:

| Table | Deduplication key |
|-------|-------------------|
| `brokers` | `broker_id` |
| `locations` | `civic_number + unit_number + street_name + street_type + city` |
| `properties` | `location_id` |
| `listings` | `listing_id + category` |

Price changes are detected on re-runs: if a listing already exists and its price has changed, the old price is appended to `price_history` before the listing is updated.

### Data Flow

```
Search page → card data + card coordinates (Phase 1)
    ↓
Detail page → page coordinates, characteristics, financial data, images, broker URL (Phase 2)
    ↓
Broker page → phone, agency name (once per unique broker per run)
    ↓
parse_helpers → clean, type-cast, normalize all values
    ↓
upsert → locations → properties → listings → images → extension tables → price_history
    ↓
data/raw/{listing_id}.json → raw snapshot saved locally
```

### Address Normalization

Raw addresses from the platform are parsed into structured components at insertion time:

```
"1095, Avenue Pratt, apt. 406 Montréal (Outremont)"
    → civic_number: "1095"
    → unit_number:  "406"
    → street_name:  "pratt"
    → street_type:  "avenue"
    → borough:      "Outremont"
    → city:         "Montréal"
```

Street type normalization: "St" → "rue", "Ave" → "avenue", "Blvd" → "boulevard", "Ch" → "chemin", etc.
Street name normalization: "St-Jacques" → "saint-jacques", "Ste-Catherine" → "sainte-catherine", etc.

A backfill script (`scripts/backfill_locations.py`) was used to retroactively parse all existing raw addresses after the normalization logic was introduced.

### Current Dataset (Montreal Island)

| Table | Count |
|-------|-------|
| Listings | 11,214 |
| Properties | 11,189 |
| Brokers | 495 |
| Locations | 11,068 |
| Images | 171,840 |
| Price history entries | 11,109 |

*Dataset includes for-sale and for-rent listings across residential and commercial categories. Multiple scraping runs performed to approach saturation.*

---

## Step 3 — Data Analysis & Price Prediction

*(Coming soon)*

Planned approach:
- Exploratory data analysis per property type and city
- Separate price prediction models per type (condo, house, plex, commercial)
- Key features: location (lat/lon), size, year built, municipal assessment, taxes, borough, property type
- Rental yield analysis: comparing for_rent vs for_sale prices at the same location
- Models: Linear Regression baseline → Random Forest → XGBoost
- Evaluation: RMSE, MAE, R²

---

## Step 4 — API

*(Coming soon)*

Planned endpoints using FastAPI:
- `GET /listings` — paginated listing search with filters
- `GET /listings/{id}` — single listing detail
- `GET /properties/{id}/price-history` — price timeline
- `POST /predict/price` — ML price prediction for a given set of features

---

## Setup & Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 18
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/PaulMbwase/real-estate-pipeline.git
cd real-estate-pipeline

# Create and activate virtual environment
python -m venv rs-env
source rs-env/Scripts/activate  # Windows Git Bash
# source rs-env/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### Configuration

Create a `.env` file at the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=real_estate
DB_USER=postgres
DB_PASSWORD=your_password

BASE_URL=https://www.your-target-site.com
TARGET_URL_RESIDENTIAL=https://www.your-target-site.com/en/properties~for-sale~montreal-island?sort=None&pageSize=20
TARGET_URL_COMMERCIAL=https://www.your-target-site.com/en/commercial-properties~for-sale~montreal-island?sort=None&pageSize=20
CITY=montreal
```

### Database Setup

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE real_estate;"

# Create all tables via SQLAlchemy models
python db/models.py
```

### Running the Scraper

```bash
python -m scraper.main
```

This launches two parallel browser processes — one for residential, one for commercial listings. To switch cities, update the target URLs in `.env` and rerun.

---

## License

This project is for educational and portfolio purposes.
