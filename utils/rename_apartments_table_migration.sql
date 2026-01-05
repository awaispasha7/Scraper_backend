-- Migration script to rename apartments_frbo_chicago to apartments_frbo
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor)

-- Step 1: Rename the table
ALTER TABLE IF EXISTS apartments_frbo_chicago RENAME TO apartments_frbo;

-- Step 2: Rename indexes (ALTER INDEX IF EXISTS works in PostgreSQL 9.5+)
ALTER INDEX IF EXISTS idx_apartments_listing_url RENAME TO idx_apartments_frbo_listing_url;
ALTER INDEX IF EXISTS idx_apartments_city RENAME TO idx_apartments_frbo_city;
ALTER INDEX IF EXISTS idx_apartments_zip_code RENAME TO idx_apartments_frbo_zip_code;
ALTER INDEX IF EXISTS idx_apartments_state RENAME TO idx_apartments_frbo_state;

-- Step 3: Rename trigger (PostgreSQL doesn't support IF EXISTS with ALTER TRIGGER RENAME, so we use a DO block)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_apartments_updated_at' AND tgrelid = 'apartments_frbo'::regclass) THEN
        ALTER TRIGGER update_apartments_updated_at ON apartments_frbo RENAME TO update_apartments_frbo_updated_at;
    END IF;
END $$;

-- Step 4: Drop and recreate RLS policies with new table name
-- Note: Policies are automatically dropped when table is renamed, but we'll recreate them explicitly
DROP POLICY IF EXISTS "Allow public read access" ON apartments_frbo;
DROP POLICY IF EXISTS "Allow authenticated insert" ON apartments_frbo;
DROP POLICY IF EXISTS "Allow authenticated update" ON apartments_frbo;
DROP POLICY IF EXISTS "Allow authenticated delete" ON apartments_frbo;

-- Recreate policies on new table name
CREATE POLICY "Allow public read access" ON apartments_frbo
    FOR SELECT
    USING (true);

CREATE POLICY "Allow authenticated insert" ON apartments_frbo
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "Allow authenticated update" ON apartments_frbo
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow authenticated delete" ON apartments_frbo
    FOR DELETE
    TO authenticated
    USING (true);

-- Note: The table already has city and state fields, so it can store data from multiple locations
-- No schema changes needed - just the rename

