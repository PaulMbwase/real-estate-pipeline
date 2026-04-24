
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

select * from brokers;

select * from listings;

select count(*) from listing_condo;

select count(*) from listing_plex;

select Count(*) from listing_commercial;
select * from locations;