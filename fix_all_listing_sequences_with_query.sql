-- SQL Script to fix sequences for ALL listing tables
-- This script finds the actual sequence names and fixes them
-- Run this in Supabase SQL Editor

-- First, let's check which sequences exist and get their current values
-- Then we'll fix them based on the max ID in each table

-- Fix sequences for all listing tables
-- For GENERATED ALWAYS AS IDENTITY columns, the sequence name follows the pattern: {table}_id_seq
-- But if that doesn't work, we can find the actual sequence name using the query below

-- Helper: Get sequence name for a table (run this for each table if needed)
-- SELECT pg_get_serial_sequence('table_name', 'id');

-- Fix all sequences based on max ID in each table
DO $$
DECLARE
    max_id_val INTEGER;
    seq_name TEXT;
BEGIN
    -- addresses
    SELECT MAX(id) INTO max_id_val FROM addresses;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('addresses', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- apartments_frbo
    SELECT MAX(id) INTO max_id_val FROM apartments_frbo;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('apartments_frbo', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- hotpads_listings
    SELECT MAX(id) INTO max_id_val FROM hotpads_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('hotpads_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- listings
    SELECT MAX(id) INTO max_id_val FROM listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- other_listings
    SELECT MAX(id) INTO max_id_val FROM other_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('other_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- redfin_listings
    SELECT MAX(id) INTO max_id_val FROM redfin_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('redfin_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- trulia_listings
    SELECT MAX(id) INTO max_id_val FROM trulia_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('trulia_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- zillow_frbo_listings
    SELECT MAX(id) INTO max_id_val FROM zillow_frbo_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('zillow_frbo_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
    
    -- zillow_fsbo_listings
    SELECT MAX(id) INTO max_id_val FROM zillow_fsbo_listings;
    IF max_id_val IS NULL THEN max_id_val := 0; END IF;
    seq_name := pg_get_serial_sequence('zillow_fsbo_listings', 'id');
    IF seq_name IS NOT NULL THEN
        EXECUTE format('SELECT setval(%L, %s, false)', seq_name, max_id_val + 1);
        RAISE NOTICE 'Fixed sequence % to %', seq_name, max_id_val + 1;
    END IF;
END $$;

