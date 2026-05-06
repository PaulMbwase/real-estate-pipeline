/*
	This file contains a collection of SQL queries used for testing and 
preprocessing during the data scraping pipeline.
	It is organized into the following three sections:
		Part 1: General Queries – Standard data validation and high-level inspections.
		Part 2: JSON Extraction – Logic for parsing and flattening 
				semi-structured data from the platform.
		Part 3: View Creation – Definitions for persistent database 
				views to streamline analysis.

*/

/*
	PART I: GENERAL QUERIES
*/

SELECT *
FROM scrape_runs 
ORDER BY id DESC;

-- Property Type Distribution
SELECT DISTINCT property_type, COUNT(*) AS Total
FROM properties
GROUP BY property_type
ORDER BY Total DESC;

-- Listings with Missing Price 
SELECT 
    COUNT(*) as listings,
    COUNT(price) as with_price,
    COUNT(*) - COUNT(price) as no_price
FROM listings;

-- Locations With Missing Geolocations
SELECT 
    COUNT(*) as total,
    COUNT(latitude) as has_coords,
    COUNT(*) - COUNT(latitude) as missing_coords,
    ROUND((COUNT(latitude)::numeric / COUNT(*)::numeric) * 100, 2) as success_rate
FROM locations;

-- General Checking 
select * from listing_commercial ORDER BY id DESC LIMIT 10 OFFSET 100;
select * from properties LIMIT 10 OFFSET 1;
select * from brokers LIMIT 10 OFFSET 10;
select * from listings LIMIT 10 OFFSET 1 ;
select * from locations LIMIT 10 OFFSET 100;
select * from scrape_runs order by id;


select listing_id, count(*) from price_history group by listing_id having count(*)>1; -- limit 10 offset 100;

--------------------------------------------------

-- City Evolution
SELECT city, COUNT(*) total
FROM locations
GROUP BY city
ORDER BY total DESC;


-- deleting double listing
-- Find for_rent listings that had the wrong sale price as their first entry
-- DELETE FROM price_history
-- WHERE id IN (
--     SELECT ph.id
--     FROM price_history ph
--     JOIN listings l ON ph.listing_id = l.id
--     WHERE l.category = 'for_rent'
--     AND ph.price > 100000  -- rental prices are never this high
-- );

-- bad price recorded
SELECT l1.listing_id, l1.price as for_sale_price, l2.price as for_rent_price
FROM listings l1
JOIN listings l2 ON l1.listing_id = l2.listing_id
WHERE l1.category = 'for_sale'
AND l2.category = 'for_rent'
AND l1.price = l2.price
ORDER BY l1.listing_id;

-- property double listings
SELECT l.* 
FROM properties AS p
JOIN listings AS l ON p.id = l.property_id
JOIN double_listing AS d ON l.listing_id = d.listing_id;



-- scraping evolution
SELECT
    (SELECT COUNT(*) FROM listings)       as listings,
    (SELECT COUNT(*) FROM properties)     as properties,
    (SELECT COUNT(*) FROM brokers)        as brokers,
    (SELECT COUNT(*) FROM locations)      as locations,
    (SELECT COUNT(*) FROM listing_condo) as condos,
	(SELECT COUNT(*) FROM listing_commercial) as commercials,
	(SELECT COUNT(*) FROM listing_plex) as plexes,
	(SELECT COUNT(*) FROM listing_images) as images,
    (SELECT COUNT(*) FROM price_history)  as price_history;


-- New listings per day
SELECT DATE(created_at), COUNT(*) 
FROM listings 
GROUP BY DATE(created_at) 
ORDER BY DATE(created_at);

-- Updated listings per day (seen again but not new)
SELECT DATE(updated_at), COUNT(*) 
FROM listings 
WHERE updated_at > created_at
GROUP BY DATE(updated_at) 
ORDER BY DATE(updated_at);

------------------

-- Stale/Delisted properties
SELECT * FROM listings 
WHERE updated_at < NOW() - INTERVAL '2 days';
----------------------------------------------------------------


-- check double category
SELECT id, listing_id, category, price 
FROM listings 
WHERE listing_id = '10093636';

-- Missing category
SELECT id, listing_id, category, price 
FROM listings 
WHERE category IS NULL 
LIMIT 5;

-- Check of column types
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('properties', 'listings', 'brokers', 'locations')
AND column_name IN ('property_id', 'listing_id', 'broker_id', 'location_id')
ORDER BY table_name;

-- check contraints
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'listings';


-- Checking the missing price
SELECT l.id, l.price, l.created_at
FROM listings l
WHERE l.price IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM price_history ph 
    WHERE ph.listing_id = l.id
);

-- orphan prices
SELECT COUNT(*) FROM price_history ph
JOIN listings l ON l.id = ph.listing_id
WHERE l.category = 'for_sale'
AND ph.price < 50000;


-- checking listing type
SELECT category, COUNT(*) AS total
FROM listings
GROUP BY category 
ORDER BY total DESC;

-----------------------------------------------------
SELECT 
	p.municipal_assessment,
	(p.financial_data ->> 'municipal_assessment') AS muni
FROM properties AS p
WHERE p.municipal_assessment IS NOT NULL;

-----------------------------------------------------------------------------
-----------------------------------------------------------------------------
------------------PART II: JSON EXTRACTION-----------------------------------
-----------------------------------------------------------------------------
SELECT DISTINCT jsonb_object_keys(characteristics) as available_fields
FROM properties
ORDER BY available_fields DESC;

SELECT DISTINCT jsonb_object_keys(financial_data) as available_fields
FROM properties
ORDER BY available_fields DESC;



SELECT 
    key, 
    count(*) AS appearance_count,
    round(count(*) * 100.0 / (SELECT count(*) FROM properties), 2) AS percent_coverage
FROM properties, 
     jsonb_object_keys(characteristics) AS key
WHERE property_type IN ('house','condo','duplex','triplex',
                        'quadruplex','quintuplex','condominium_house',
                        'loft_studio','cottage','mobile_home')
GROUP BY key
ORDER BY appearance_count DESC
LIMIT 30;

SELECT p.characteristics->> 'net_area' as net_area
FROM properties as p;    

select * from properties limit 10 offset 1000;


select id, location_id
from properties
where characteristics ? 'year_built';

------------------------------------------------------------------------------
------------------------------------------------------------------------------
------------------------------------------------------------------------------
------------------- PART III: CREATING VIEWS ---------------------------------
------------------------------------------------------------------------------
-- Residential for-sale base view
CREATE VIEW v_residential_sale AS
SELECT 
    l.id as listing_id, l.listing_id as platform_id,
    l.price, l.created_at, l.updated_at,
    p.property_type, p.size_sqft, p.bedrooms, p.bathrooms,
    p.year_built, p.parking, p.garage, p.pool, p.basement,
    p.municipal_assessment, p.school_taxes, p.municipal_taxes,
    p.characteristics,
    loc.city, loc.borough, loc.latitude, loc.longitude,
    loc.street_type, loc.street_name
FROM listings l
JOIN properties p  ON l.property_id = p.id
JOIN locations loc ON p.location_id  = loc.id
WHERE l.category = 'for_sale'
AND l.status     = 'Active'
AND p.property_type IN ('house','condo','duplex','triplex',
                        'quadruplex','quintuplex','condominium_house',
                        'loft_studio','cottage','mobile_home');

-- Commercial base view
CREATE VIEW v_commercial_sale AS
SELECT
    l.id as listing_id, l.listing_id as centris_id,
    l.price, l.category, l.created_at,
    p.property_type, p.size_sqft, p.municipal_assessment,
    lc.zoning, lc.business_type, lc.ceiling_height,
    lc.rent_per_sqft, lc.rent_period,
    loc.city, loc.borough, loc.latitude, loc.longitude
FROM listings l
JOIN properties p        ON l.property_id  = p.id
JOIN locations loc       ON p.location_id  = loc.id
LEFT JOIN listing_commercial lc ON l.id   = lc.listing_id
WHERE p.property_type IN ('commercial','industrial','office',
                          'business','income_properties');

-- Investment yield view — joins for_sale and for_rent at same location
CREATE VIEW v_investment_yield AS
SELECT
    ls.listing_id as sale_listing_id,
    lr.listing_id as rent_listing_id,
    ls.price      as sale_price,
    lr.price      as monthly_rent,
    ROUND((lr.price * 12 / ls.price) * 100, 2) as gross_yield_pct,
    p.property_type, p.size_sqft, p.bedrooms,
    loc.city, loc.borough, loc.latitude, loc.longitude
FROM listings ls
JOIN listings lr   ON ls.listing_id = lr.listing_id  -- same centris ID
JOIN properties p  ON ls.property_id = p.id
JOIN locations loc ON p.location_id  = loc.id
WHERE ls.category = 'for_sale'
AND lr.category   = 'for_rent'
AND ls.price IS NOT NULL
AND lr.price IS NOT NULL;





-- CREATE OR REPLACE VIEW v_residential_sale AS
SELECT
    l.id                                as listing_id,
    l.listing_id                        as centris_id,
    l.price,
    l.created_at,
    l.updated_at,
    p.property_type,
    p.size_sqft,
    p.bedrooms,
    p.bathrooms,
    p.half_bathrooms,
    p.year_built,
    p.parking,
    p.garage,
    p.pool,
    p.basement,
    p.municipal_assessment,
    p.school_taxes,
    p.municipal_taxes,
    p.lot_size_sqft,
    p.floors,
    p.total_rooms,
    loc.city,
    loc.borough,
    loc.latitude,
    loc.longitude,
    loc.street_type
FROM listings l
JOIN properties p   ON l.property_id = p.id
JOIN locations loc  ON p.location_id  = loc.id
WHERE l.category     = 'for_sale'
AND   l.status       = 'Active'
AND   p.property_type IN (
    'house', 'condo', 'duplex', 'triplex',
    'quadruplex', 'quintuplex', 'condominium_house',
    'loft_studio', 'cottage', 'mobile_home'
);




-------------------------------------------------------------------------------
-- Backing up a db on terminal
-- pg_dump -U postgres -d real_estate -f data/exports/backup_v4_montreal_complete.sql

-- -- truncating a db
-- TRUNCATE TABLE listing_images, price_history, listing_condo, listing_plex, listing_commercial, listings, properties, locations, brokers 
-- RESTART IDENTITY CASCADE;