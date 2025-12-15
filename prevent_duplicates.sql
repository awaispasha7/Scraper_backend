-- Part 1: Clean up duplicates in zillow_frbo_listings
-- Keep the row with the HIGHEST ID (latest), delete older duplicates with same URL
DELETE FROM zillow_frbo_listings
WHERE id NOT IN (
    SELECT MAX(id)
    FROM zillow_frbo_listings
    GROUP BY url
);

-- Part 2: Add Unique Constraint to zillow_frbo_listings
-- This ensures 'upsert' works and no new duplicates can be inserted
ALTER TABLE zillow_frbo_listings 
ADD CONSTRAINT unique_url_frbo UNIQUE (url);


-- Part 3: Clean up duplicates in zillow_fsbo_listings
DELETE FROM zillow_fsbo_listings
WHERE id NOT IN (
    SELECT MAX(id)
    FROM zillow_fsbo_listings
    GROUP BY detail_url
);

-- Part 4: Add Unique Constraint to zillow_fsbo_listings
ALTER TABLE zillow_fsbo_listings 
ADD CONSTRAINT unique_detail_url_fsbo UNIQUE (detail_url);
