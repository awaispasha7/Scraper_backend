"""
Script to fix sequences for all listing tables in Supabase.
This resolves duplicate key errors and ensures IDs are sequential.

Tables with integer ID columns that use sequences:
- addresses
- apartments_frbo
- hotpads_listings
- listings
- other_listings
- redfin_listings
- trulia_listings
- zillow_frbo_listings
- zillow_fsbo_listings
"""
import os
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Add Scraper_backend to sys.path to import utils
backend_root = Path(__file__).resolve().parents[0]  # This script is in Scraper_backend
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

# Load environment variables from project root (Scraper_backend/.env)
env_path = backend_root / '.env'
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Supabase credentials not found in environment variables.")
    print("Please ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_max_id(table_name: str) -> int:
    """Fetches the maximum ID from a given table."""
    try:
        response = supabase.table(table_name).select("id").order("id", desc=True).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["id"]
        return 0
    except Exception as e:
        print(f"   [ERROR] Could not get max ID: {e}")
        return None

def get_total_records(table_name: str) -> int:
    """Fetches the total number of records in a given table."""
    try:
        response = supabase.table(table_name).select("count", count="exact").execute()
        return response.count
    except Exception as e:
        print(f"   [ERROR] Could not get count: {e}")
        return None

def get_sequence_name(table_name: str, column_name: str = "id") -> str:
    """Gets the actual sequence name for an IDENTITY column using PostgreSQL system function."""
    try:
        # Use PostgreSQL's pg_get_serial_sequence function to get the sequence name
        # For IDENTITY columns, this should work, but we need to use RPC or raw SQL
        # Since Supabase client doesn't support raw SQL easily, we'll try the standard naming
        # pattern first: {table_name}_{column_name}_seq
        # For IDENTITY columns, it should be: {table_name}_{column_name}_seq
        
        # Actually, we can use a query to get the sequence name from information_schema
        # But Supabase client limitations... let's try using RPC if available, or just use standard pattern
        # For now, return the standard pattern - user can verify in SQL if needed
        return f"{table_name}_{column_name}_seq"
    except Exception as e:
        print(f"   [ERROR] Could not determine sequence name: {e}")
        return f"{table_name}_{column_name}_seq"

if __name__ == "__main__":
    print("=" * 80)
    print("Fixing sequences for ALL listing tables in Supabase")
    print("=" * 80)
    
    # All tables with integer ID columns that use sequences
    tables = [
        "addresses",
        "apartments_frbo",
        "hotpads_listings",
        "listings",
        "other_listings",
        "redfin_listings",
        "trulia_listings",
        "zillow_frbo_listings",
        "zillow_fsbo_listings"
    ]
    
    results = []
    
    print("\n1. Analyzing all tables...\n")
    
    for table_name in tables:
        print(f"   Analyzing: {table_name}")
        max_id = get_max_id(table_name)
        total_records = get_total_records(table_name)
        
        if max_id is not None and total_records is not None:
            next_sequence_value = max_id + 1
            results.append({
                "table": table_name,
                "max_id": max_id,
                "total_records": total_records,
                "next_sequence_value": next_sequence_value,
                "sequence_name": f"{table_name}_id_seq"
            })
            print(f"      Max ID: {max_id}, Total Records: {total_records}, Next ID: {next_sequence_value}")
        else:
            print(f"      [SKIP] Could not analyze this table")
        print()
    
    print("=" * 80)
    print("SQL COMMANDS TO FIX ALL SEQUENCES")
    print("=" * 80)
    print("\nRun these SQL commands in your Supabase SQL Editor:\n")
    print("-- Fix sequences for all listing tables")
    print("-- Run all commands at once or individually\n")
    
    for result in results:
        print(f"-- {result['table']}: Max ID = {result['max_id']}, Total Records = {result['total_records']}")
        print(f"SELECT setval('{result['sequence_name']}', {result['next_sequence_value']}, false);")
        print()
    
    print("=" * 80)
    print("COMPLETE SQL BLOCK (copy and paste all at once)")
    print("=" * 80)
    print()
    print("-- Fix all sequences at once")
    for result in results:
        print(f"SELECT setval('{result['sequence_name']}', {result['next_sequence_value']}, false);")
    
    print("\n" + "=" * 80)
    print("Steps to fix:")
    print("=" * 80)
    print("1. Open your Supabase Dashboard")
    print("2. Go to SQL Editor")
    print("3. Copy and paste the SQL commands above (either individual or the complete block)")
    print("4. Click 'Run'")
    print("\nThis will reset all sequences to the correct values.")
    print("After this, new inserts will use sequential IDs starting from the correct values.")
    print("\n[SUCCESS] Analysis complete!")

