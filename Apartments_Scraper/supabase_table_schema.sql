-- SQL script to create apartments_frbo_chicago table in Supabase
-- Run this in the Supabase SQL Editor (Dashboard > SQL Editor)

-- Create the table
CREATE TABLE IF NOT EXISTS apartments_frbo_chicago (
    id BIGSERIAL PRIMARY KEY,
    listing_url TEXT UNIQUE NOT NULL,
    title TEXT,
    price TEXT,
    beds TEXT,
    baths TEXT,
    sqft TEXT,
    owner_name TEXT,
    owner_email TEXT,
    phone_numbers TEXT,
    full_address TEXT,
    street TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    neighborhood TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_apartments_listing_url ON apartments_frbo_chicago(listing_url);
CREATE INDEX IF NOT EXISTS idx_apartments_city ON apartments_frbo_chicago(city);
CREATE INDEX IF NOT EXISTS idx_apartments_zip_code ON apartments_frbo_chicago(zip_code);
CREATE INDEX IF NOT EXISTS idx_apartments_state ON apartments_frbo_chicago(state);

-- Create a function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_apartments_updated_at 
    BEFORE UPDATE ON apartments_frbo_chicago
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (RLS) - adjust policies as needed
ALTER TABLE apartments_frbo_chicago ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow public read access (adjust as needed)
CREATE POLICY "Allow public read access" ON apartments_frbo_chicago
    FOR SELECT
    USING (true);

-- Create a policy to allow authenticated users to insert/update (adjust as needed)
CREATE POLICY "Allow authenticated insert" ON apartments_frbo_chicago
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Allow authenticated update" ON apartments_frbo_chicago
    FOR UPDATE
    USING (auth.role() = 'authenticated');

