-- SQL script to create other_listings table in Supabase
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor)

-- Create the table for unknown/unsupported platforms
CREATE TABLE IF NOT EXISTS other_listings (
    id integer GENERATED ALWAYS AS IDENTITY NOT NULL,
    platform text NOT NULL,
    url text NOT NULL UNIQUE,
    address text,
    price text,
    beds text,
    baths text,
    square_feet text,
    city text,
    state text,
    zip_code text,
    raw_data jsonb,
    address_hash text,
    enrichment_status text DEFAULT 'never_checked'::text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT other_listings_pkey PRIMARY KEY (id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_other_listings_url ON other_listings(url);
CREATE INDEX IF NOT EXISTS idx_other_listings_platform ON other_listings(platform);
CREATE INDEX IF NOT EXISTS idx_other_listings_address_hash ON other_listings(address_hash);
CREATE INDEX IF NOT EXISTS idx_other_listings_city ON other_listings(city);
CREATE INDEX IF NOT EXISTS idx_other_listings_state ON other_listings(state);

-- Create a function to automatically update updated_at timestamp (if it doesn't exist)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_other_listings_updated_at ON other_listings;
CREATE TRIGGER update_other_listings_updated_at 
    BEFORE UPDATE ON other_listings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS)
ALTER TABLE other_listings ENABLE ROW LEVEL SECURITY;

-- Create policies
DROP POLICY IF EXISTS "Allow public read access" ON other_listings;
CREATE POLICY "Allow public read access" ON other_listings
    FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Allow authenticated insert" ON other_listings;
CREATE POLICY "Allow authenticated insert" ON other_listings
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated update" ON other_listings;
CREATE POLICY "Allow authenticated update" ON other_listings
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Allow authenticated delete" ON other_listings;
CREATE POLICY "Allow authenticated delete" ON other_listings
    FOR DELETE
    TO authenticated
    USING (true);

