-- SQL Script to reset Hotpads sequence to start from 1
-- WARNING: This will DELETE ALL existing records in hotpads_listings
-- Run this in Supabase SQL Editor

-- Step 1: Delete all existing records
DELETE FROM hotpads_listings;

-- Step 2: Reset the sequence to start from 1
-- For GENERATED ALWAYS AS IDENTITY or BIGSERIAL columns
ALTER TABLE hotpads_listings ALTER COLUMN id RESTART WITH 1;

-- Verify the table is empty
SELECT COUNT(*) as record_count FROM hotpads_listings;

