-- SQL Script to fix sequences for ALL listing tables
-- For GENERATED ALWAYS AS IDENTITY columns, use ALTER TABLE ... RESTART instead of setval()
-- Run this in Supabase SQL Editor

-- Fix sequences for all listing tables using ALTER TABLE ... RESTART
-- This is the correct syntax for IDENTITY columns

DO $$
DECLARE
    max_id_val INTEGER;
BEGIN
    -- addresses
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM addresses;
    EXECUTE format('ALTER TABLE addresses ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed addresses sequence to start from %', max_id_val + 1;
    
    -- apartments_frbo
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM apartments_frbo;
    EXECUTE format('ALTER TABLE apartments_frbo ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed apartments_frbo sequence to start from %', max_id_val + 1;
    
    -- hotpads_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM hotpads_listings;
    EXECUTE format('ALTER TABLE hotpads_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed hotpads_listings sequence to start from %', max_id_val + 1;
    
    -- listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM listings;
    EXECUTE format('ALTER TABLE listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed listings sequence to start from %', max_id_val + 1;
    
    -- other_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM other_listings;
    EXECUTE format('ALTER TABLE other_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed other_listings sequence to start from %', max_id_val + 1;
    
    -- redfin_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM redfin_listings;
    EXECUTE format('ALTER TABLE redfin_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed redfin_listings sequence to start from %', max_id_val + 1;
    
    -- trulia_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM trulia_listings;
    EXECUTE format('ALTER TABLE trulia_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed trulia_listings sequence to start from %', max_id_val + 1;
    
    -- zillow_frbo_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM zillow_frbo_listings;
    EXECUTE format('ALTER TABLE zillow_frbo_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed zillow_frbo_listings sequence to start from %', max_id_val + 1;
    
    -- zillow_fsbo_listings
    SELECT COALESCE(MAX(id), 0) INTO max_id_val FROM zillow_fsbo_listings;
    EXECUTE format('ALTER TABLE zillow_fsbo_listings ALTER COLUMN id RESTART WITH %s', max_id_val + 1);
    RAISE NOTICE 'Fixed zillow_fsbo_listings sequence to start from %', max_id_val + 1;
END $$;

