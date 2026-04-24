CREATE TABLE IF NOT EXISTS brokers (
    id              SERIAL PRIMARY KEY,
    broker_id      VARCHAR(50) UNIQUE NOT NULL, -- source platform ID
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    contact_url     TEXT,
    agency_name     VARCHAR(255),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS locations (
    id              SERIAL PRIMARY KEY,
    address         VARCHAR(255),
    province        VARCHAR(50) NOT NULL,
    postal_code     VARCHAR(10),
    neighborhood    VARCHAR(150),
    latitude        DECIMAL(9,6),
    longitude       DECIMAL(9,6),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS properties (
    id              SERIAL PRIMARY KEY,
    location_id     INT REFERENCES locations(id),
    property_id     VARCHAR(50) UNIQUE NOT NULL,   -- source platform ID
    property_type   VARCHAR(50) NOT NULL,
    year_built      SMALLINT,
    size_sqft       DECIMAL(10,2),
    lot_size_sqft   DECIMAL(10,2),
    floors          SMALLINT,
    total_rooms     SMALLINT,
    bedrooms        SMALLINT,
    bathrooms       SMALLINT,
    half_bathrooms  SMALLINT,
    parking         SMALLINT,
    garage          BOOLEAN DEFAULT FALSE,
    pool            BOOLEAN DEFAULT FALSE,
    basement        BOOLEAN DEFAULT FALSE,
    waterfront      BOOLEAN DEFAULT FALSE,
    municipal_assessment    DECIMAL(12,2),  -- total assessed value
    assessment_year         SMALLINT,       -- year of assessment
    lot_assessment          DECIMAL(12,2),  -- lot portion
    building_assessment     DECIMAL(12,2), -- building portion

    -- Annual expenses
    municipal_taxes         DECIMAL(10,2),
    school_taxes            DECIMAL(10,2),
    characteristics JSONB,
    financial_data  JSONB,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listings (
    id              SERIAL PRIMARY KEY,
    property_id     INT NOT NULL REFERENCES properties(id),
    broker_id       INT REFERENCES brokers(id),
    listing_id      VARCHAR(50) UNIQUE NOT NULL, -- The source platform ID
    category        VARCHAR(50) NOT NULL,        -- e.g., 'For Sale', 'For Rent'
    price           DECIMAL(12, 2) NOT NULL,
    status          VARCHAR(20) DEFAULT 'Active', -- e.g., 'Active', 'Sold', 'Pending'
    description     TEXT,                         -- The marketing blurb
    url             TEXT,                         -- Link to the original page
    list_date       DATE DEFAULT CURRENT_DATE,
    sold_date       DATE,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id              SERIAL PRIMARY KEY,
    listing_id      INT NOT NULL REFERENCES listings(id),
    price           DECIMAL(12,2) NOT NULL,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listing_images (
    id              SERIAL PRIMARY KEY,
    listing_id      INT NOT NULL REFERENCES listings(id),
    image_url       TEXT NOT NULL,
    is_primary      BOOLEAN DEFAULT FALSE,
    display_order   SMALLINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS listing_condo (
    id              SERIAL PRIMARY KEY,
    listing_id      INT NOT NULL UNIQUE REFERENCES listings(id),
    condo_fees      DECIMAL(8,2),
    floor_number    SMALLINT,
    total_floors    SMALLINT,
    locker          BOOLEAN DEFAULT FALSE

);

CREATE TABLE IF NOT EXISTS listing_plex (
    id              SERIAL PRIMARY KEY,
    listing_id      INT NOT NULL UNIQUE REFERENCES listings(id),
    units           SMALLINT NOT NULL,
    rental_income   DECIMAL(12, 2),
    kitchens        SMALLINT
);

CREATE TABLE IF NOT EXISTS listing_commercial (
    id              SERIAL PRIMARY KEY,
    listing_id      INT NOT NULL UNIQUE REFERENCES listings(id),
    zoning          VARCHAR(100),
    business_type   VARCHAR(50),
    ceiling_height  DECIMAL(5,2)
);

