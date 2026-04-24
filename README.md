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

**Target data:** Residential and commercial property listings in the Montreal metropolitan area (Quebec, Canada), with the architecture designed to support province-wide scraping and future extension to other data sources.

**Key features:**
- Dynamic scraping of JavaScript-rendered pages using Playwright
- Normalized relational schema with 9 tables
- Price history tracking across scraping runs
- Geolocation via embedded page metadata with Nominatim fallback
- Dynamic financial data extraction (municipal assessment, taxes) stored as JSONB
- Anti-scraping protections: random delays, user agent rotation, retry logic
- Parallel scraping of residential and commercial listings via multiprocessing

---

## Project Structure

```
real-estate-pipeline/
├── db/
│   ├── schema.sql          # Raw SQL schema (reference)
│   ├── queries.sql         # Raw SQL queries (occasional db checking)
│   └── models.py           # SQLAlchemy ORM models (source of truth)
├── scraper/
│   ├── __init__.py
│   ├── main.py             # Pipeline orchestration + DB insertion
│   ├── scraper.py          # Playwright scraping functions
│   ├── utils.py            # Helper functions (safe_text, geocoding)
│   └── parse_helpers.py    # Data cleaning and type parsing
├── analysis/
│   └── notebooks/          # Jupyter notebooks for EDA and ML
├── api/
│   └── main.py             # FastAPI application (coming soon)
├── data/
│   ├── raw/                # Raw JSON snapshots per listing (gitignored)
│   ├── processed/          # Cleaned data ready for ML (gitignored)
│   └── exports/            # Database backups and CSV exports (gitignored)
├── .env                    # Credentials and target URLs (never committed)
├── .gitignore
├── .gitattributes
├── requirements.txt
└── README.md
```

---

## Step 1 — Database Design

### Design Philosophy

The schema follows **3rd Normal Form (3NF)** to eliminate data redundancy. The core principle is that information is stored exactly once and referenced by foreign keys everywhere else.

For example — broker information lives in the `brokers` table. If a broker has 50 listings, their phone number is stored once, not 50 times. An update to a broker's contact details requires changing a single row.

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
Stores geographic information, shared across multiple properties at the same address.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `address` | VARCHAR(255) | Full civic address |
| `province` | VARCHAR(50) | Province code (e.g. QC) |
| `postal_code` | VARCHAR(10) | Postal code |
| `neighborhood` | VARCHAR(150) | Neighborhood name |
| `latitude` | DECIMAL(9,6) | GPS latitude |
| `longitude` | DECIMAL(9,6) | GPS longitude |
| `created_at` | TIMESTAMP | Record insertion time |

> Coordinates are extracted directly from schema.org metadata embedded in listing pages. A Nominatim (OpenStreetMap) geocoding fallback is used when metadata is absent.

---

#### `properties`
Represents the physical asset — the building or land itself, independent of any listing offer.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `location_id` | INT FK | Reference to `locations` |
| `property_id` | VARCHAR(50) | Source platform property ID |
| `property_type` | VARCHAR(50) | Normalized type (condo, house, duplex, etc.) |
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
| `characteristics` | JSONB | All carac-container key-value pairs |
| `created_at` | TIMESTAMP | Record insertion time |

> `financial_data` and `characteristics` use PostgreSQL's JSONB type to store dynamic, property-type-specific data without schema changes. Both columns are fully queryable and indexable.

---

#### `listings`
Represents the commercial offer — the act of putting a property on the market. One property can have multiple listings over time (re-listed, or simultaneously for sale and for rent).

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL PK | Internal primary key |
| `property_id` | INT FK | Reference to `properties` |
| `broker_id` | INT FK | Reference to `brokers` (nullable) |
| `listing_id` | VARCHAR(50) | Source platform listing ID |
| `category` | VARCHAR(50) | Transaction type: `for_sale` or `for_rent` |
| `price` | DECIMAL(12,2) | Asking price |
| `status` | VARCHAR(20) | Active, Sold, Expired |
| `description` | TEXT | Marketing description |
| `url` | TEXT | Source listing URL |
| `list_date` | DATE | Date first listed |
| `sold_date` | DATE | Date sold (if applicable) |
| `updated_at` | TIMESTAMP | Last modification time |
| `created_at` | TIMESTAMP | Record insertion time |

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

---

### Key Design Decisions

**Base + extension model** — Rather than 5 separate tables per listing type (condo, plex, commercial, etc.), shared fields live in a base `properties` table and type-specific fields extend it. This avoids duplicating 15+ columns across tables and allows cross-type queries with a single `JOIN`.

**Separation of property and listing** — A `property` is the physical asset; a `listing` is the offer. This distinction allows tracking a property that was listed, taken off the market, and re-listed at a different price — each as a separate listing referencing the same property.

**JSONB for dynamic data** — Financial details and property characteristics vary significantly by listing type. Storing them as JSONB avoids schema migrations every time a new field appears, while remaining fully queryable in PostgreSQL.

**Price history as time-series** — Instead of overwriting prices, every change is appended to `price_history`. This enables tracking market movements over time and is a strong ML feature.

---

## Step 2 — Scraping Pipeline

### Architecture

The scraper is split across four files with clear responsibilities:

```
scraper/main.py         → Orchestration, DB insertion, pipeline loop
scraper/scraper.py      → Playwright page interactions
scraper/utils.py        → Safe extraction helpers, geocoding
scraper/parse_helpers.py → Data cleaning, type casting, normalization
```

### Two-Phase Scraping Strategy

**Phase 1 — Search results pages**

Each search results page yields up to 20 listing cards. For each card, the scraper extracts:
- Listing URL and platform ID
- Category (property type + transaction type)
- Price
- Address
- Bedroom and bathroom counts

**Phase 2 — Listing detail pages**

Each listing URL is visited individually to extract deeper features:
- GPS coordinates from `<meta itemprop="latitude/longitude">` schema.org tags
- All characteristics dynamically from `.carac-container` elements
- Financial details (municipal assessment, taxes) from the financial details table
- Broker profile URL
- Property images from `data-photo-urls` attribute
- Marketing description

### Parallel Processing

Residential and commercial listings are scraped simultaneously using Python's `multiprocessing` module. Each process runs its own independent browser instance and event loop, writing to the same PostgreSQL database via upsert operations that prevent conflicts.

```python
p1 = multiprocessing.Process(target=start_scraper, args=(TARGET_URL_RESIDENTIAL,))
p2 = multiprocessing.Process(target=start_scraper, args=(TARGET_URL_COMMERCIAL,))
```

### Anti-Scraping Protections

| Protection | Implementation |
|-----------|----------------|
| Random delays | `asyncio.sleep(random.uniform(1.5, 4.0))` between listings |
| User agent rotation | Random selection from a pool of real browser user agents |
| Network retry | `safe_goto()` retries failed navigation up to 3 times with exponential backoff |
| Network check | `wait_for_network()` detects connectivity loss at the start of each page |
| Broker deduplication | Broker pages are visited at most once per run via an in-memory cache |

### Data Insertion Strategy

All insertions use **upsert logic** — check if the record exists before inserting. This means the scraper can be safely restarted without duplicating data.

Price changes are detected on re-runs: if a listing already exists and its price has changed, the old price is appended to `price_history` before updating the listing.

### Data Flow

```
Search page → card data (Phase 1)
    ↓
Detail page → coordinates, characteristics, financial data, images, broker URL (Phase 2)
    ↓
Broker page → phone, agency name (once per unique broker)
    ↓
parse_helpers → clean, type-cast, normalize all values
    ↓
upsert → locations → properties → listings → images → extension tables → price_history
    ↓
data/raw/{property_id}.json → raw snapshot saved locally
```

### Current Dataset (Montreal Island)

| Table | Count |
|-------|-------|
| Listings | 5,636 |
| Properties | 5,636 |
| Brokers | 396 |
| Locations | 5,616 |
| Images | 103,914 |
| Price history entries | 5,550 |

---

## Step 3 — Data Analysis & Price Prediction

*(Coming soon)*

Planned approach:
- Exploratory data analysis per property type
- Separate price prediction models per type (condo, house, plex, commercial)
- Key features: location (lat/lon), size, year built, municipal assessment, taxes, neighborhood
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
git clone https://github.com/YOUR_USERNAME/real-estate-pipeline.git
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

This launches two parallel browser processes — one for residential, one for commercial listings.

---

## License

This project is for educational and portfolio purposes.
