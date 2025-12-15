-- =========================================================================
-- ROBUST DATABASE FIX SCRIPT
-- Purpose: Fix "Duplicate Key" errors by syncing ID sequences for ALL scrapers
-- Uses pg_get_serial_sequence to automatically find the correct counter name
-- Run this in Supabase Dashboard > SQL Editor
-- =========================================================================

-- 1. Fix Zillow FSBO Sequence
SELECT setval(pg_get_serial_sequence('zillow_fsbo_listings', 'id'), (SELECT COALESCE(MAX(id), 0) + 1 FROM zillow_fsbo_listings), false);

-- 2. Fix Zillow FRBO Sequence
SELECT setval(pg_get_serial_sequence('zillow_frbo_listings', 'id'), (SELECT COALESCE(MAX(id), 0) + 1 FROM zillow_frbo_listings), false);

-- 3. Fix Hotpads Sequence
SELECT setval(pg_get_serial_sequence('hotpads_listings', 'id'), (SELECT COALESCE(MAX(id), 0) + 1 FROM hotpads_listings), false);

-- 4. Fix Apartments Sequence
SELECT setval(pg_get_serial_sequence('apartments_frbo_chicago', 'id'), (SELECT COALESCE(MAX(id), 0) + 1 FROM apartments_frbo_chicago), false);

-- Done! Now your scrapers can save data without errors.
