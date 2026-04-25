
SELECT DISTINCT property_type, COUNT(*) AS Total
FROM properties
GROUP BY property_type
ORDER BY Total DESC;


SELECT 
    COUNT(*) as listings,
    COUNT(price) as with_price,
    COUNT(*) - COUNT(price) as no_price
FROM listings;

SELECT 
	COUNT(*) AS locations,
	COUNT(latitude) as with_geo,
	COUNT(*) - COUNT(latitude) as no_geo
FROM 
	locations;

SELECT count(*) from listings;

select * from properties LIMIT 10 OFFSET 10;

select * from brokers LIMIT 10 OFFSET 50;

select * from listings LIMIT 10 OFFSET 100;

select count(*) from listing_condo;

select count(*) from listing_plex;

select Count(*) from listing_commercial;
select * from locations;

------------------------------------
-- Check of string presence on the property_id
SELECT property_id 
FROM properties 
WHERE property_id ~ '[^0-9]'
LIMIT 10;

-- Check of column types
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('properties', 'listings', 'brokers', 'locations')
AND column_name IN ('property_id', 'listing_id', 'broker_id', 'location_id')
ORDER BY table_name;

-- Checking whether the price file can be stored in the property's characteristcs

SELECT p.id, p.property_id, p.characteristics
FROM properties AS p
JOIN listings AS l ON p.id = l.id
WHERE l.price IS NULL;

-- Checking the missing price
SELECT l.id, l.price, l.created_at
FROM listings l
WHERE l.price IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM price_history ph 
    WHERE ph.listing_id = l.id
);


-- Altering the database for commercial rental listing
ALTER TABLE listing_commercial 
ADD COLUMN rent_per_sqft DECIMAL(8,2),
ADD COLUMN rent_period VARCHAR(20);  -- 'yearly', 'monthly'