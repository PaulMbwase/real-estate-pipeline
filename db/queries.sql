
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

select * from listing_commercial ORDER BY id DESC LIMIT 10 OFFSET 10;

select * from properties LIMIT 10 OFFSET 1;

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

-- orphan prices
SELECT COUNT(*) FROM price_history ph
JOIN listings l ON l.id = ph.listing_id
WHERE l.category = 'for_sale'
AND ph.price < 50000;

-- Deleting the ophan price
-- DELETE FROM price_history ph
-- WHERE EXISTS (
--     SELECT 1 FROM listings l
--     WHERE l.id = ph.listing_id
--     AND l.category = 'for_sale'
--     AND ph.price < 50000
-- );

-- updating 
-- UPDATE listings l
-- SET price = ph.price
-- FROM price_history ph
-- WHERE ph.listing_id = l.id
-- AND l.category = 'for_sale'
-- AND l.price < 50000;

-- deleting the altered price
-- DELETE FROM listing_condo
-- WHERE listing_id IN (
--     SELECT id FROM listings 
--     WHERE category = 'for_sale' AND price < 50000
-- );

-- DELETE FROM listings 
-- WHERE category = 'for_sale' 
-- AND price < 50000;

-- Altering the database for commercial rental listing
-- ALTER TABLE listing_commercial 
-- ADD COLUMN rent_per_sqft DECIMAL(8,2),
-- ADD COLUMN rent_period VARCHAR(20);  -- 'yearly', 'monthly'

-- checking listing type
SELECT category, COUNT(*) AS total
FROM listings
GROUP BY category 
ORDER BY total DESC;

-- Altering the price_history table 
-- ALTER TABLE price_history DROP CONSTRAINT price_history_listing_id_key;

select * from listings  WHERE listing_id = '16747435';

-- Restore the sale price for the corrupted listing
UPDATE listings 
SET price = 51000000 
WHERE listing_id = '20462471' AND category = 'for_sale';

-- Delete the 'fake' price history entry created by the mistake
DELETE FROM price_history 
WHERE listing_id = (SELECT id FROM listings WHERE listing_id = '20462471' AND category = 'for_sale')
AND price = 19.75;