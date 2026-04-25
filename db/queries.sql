
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

select * from listings LIMIT 10 OFFSET 1 ;

select count(*) from listing_condo;

select count(*) from listing_plex;

select Count(*) from listing_commercial;
select * from locations LIMIT 10 OFFSET 1;

select l.*
from (select listing_id, count(*) as total 
from listings 
group by listing_id) as test
join listings as l on l.listing_id = test.listing_id
where total > 1
order by l.listing_id ;

-- City Evolution
SELECT city, COUNT(*) total
FROM locations
GROUP BY city
ORDER BY total DESC;

-- scraping evolution
SELECT 
    (SELECT COUNT(*) FROM listings) as total_listings,
    (SELECT COUNT(*) FROM properties) as total_properties,
    (SELECT COUNT(*) FROM brokers) as total_brokers,
    (SELECT COUNT(*) FROM locations) as total_locations;

-- checking the geocode 
SELECT 
    COUNT(*) as total,
    COUNT(latitude) as has_coords,
    COUNT(*) - COUNT(latitude) as missing_coords,
    ROUND((COUNT(latitude)::numeric / COUNT(*)::numeric) * 100, 2) as success_rate
FROM locations;

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


-- Stale/Delisted properties
SELECT * FROM listings 
WHERE updated_at < NOW() - INTERVAL '1 days';
------------------------------------
-- Check of string presence on the property_id
SELECT property_id 
FROM properties 
WHERE property_id ~ '[^0-9]'
LIMIT 10;



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
-- UPDATE listings 
-- SET price = 51000000 
-- WHERE listing_id = '20462471' AND category = 'for_sale';

-- Delete the 'fake' price history entry created by the mistake
-- DELETE FROM price_history 
-- WHERE listing_id = (SELECT id FROM listings WHERE listing_id = '20462471' AND category = 'for_sale')
-- AND price = 19.75;

-- Altering location table
-- ALTER TABLE locations ADD COLUMN civic_number  VARCHAR(20);
-- ALTER TABLE locations ADD COLUMN unit_number   VARCHAR(20);
-- ALTER TABLE locations ADD COLUMN street_name   VARCHAR(100);
-- ALTER TABLE locations ADD COLUMN street_type   VARCHAR(20);
-- ALTER TABLE locations ADD COLUMN borough       VARCHAR(100);
-- ALTER TABLE locations ADD COLUMN city          VARCHAR(100);
-- ALTER TABLE locations ADD COLUMN postal_code   VARCHAR(10);
-- ALTER TABLE locations RENAME COLUMN address TO raw_address;

-- Droping property_id in properties listing
-- ALTER TABLE properties DROP COLUMN property_id;