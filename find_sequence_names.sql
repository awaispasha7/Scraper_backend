-- Query to find the actual sequence names for all tables
-- Run this first to see what sequences actually exist

SELECT 
    schemaname,
    sequencename,
    last_value
FROM pg_sequences
WHERE sequencename LIKE '%_id_seq'
ORDER BY sequencename;

-- Alternative: Find sequences for specific tables using pg_get_serial_sequence
SELECT 
    'addresses' as table_name,
    pg_get_serial_sequence('addresses', 'id') as sequence_name
UNION ALL
SELECT 
    'apartments_frbo' as table_name,
    pg_get_serial_sequence('apartments_frbo', 'id') as sequence_name
UNION ALL
SELECT 
    'hotpads_listings' as table_name,
    pg_get_serial_sequence('hotpads_listings', 'id') as sequence_name
UNION ALL
SELECT 
    'listings' as table_name,
    pg_get_serial_sequence('listings', 'id') as sequence_name
UNION ALL
SELECT 
    'other_listings' as table_name,
    pg_get_serial_sequence('other_listings', 'id') as sequence_name
UNION ALL
SELECT 
    'redfin_listings' as table_name,
    pg_get_serial_sequence('redfin_listings', 'id') as sequence_name
UNION ALL
SELECT 
    'trulia_listings' as table_name,
    pg_get_serial_sequence('trulia_listings', 'id') as sequence_name
UNION ALL
SELECT 
    'zillow_frbo_listings' as table_name,
    pg_get_serial_sequence('zillow_frbo_listings', 'id') as sequence_name
UNION ALL
SELECT 
    'zillow_fsbo_listings' as table_name,
    pg_get_serial_sequence('zillow_fsbo_listings', 'id') as sequence_name;

