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
    response = supabase.table(table_name).select("id").order("id", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]["id"]
    return 0

def get_total_records(table_name: str) -> int:
    """Fetches the total number of records in a given table."""
    response = supabase.table(table_name).select("count", count="exact").execute()
    return response.count

if __name__ == "__main__":
    print("=" * 60)
    print("Fixing hotpads_listings table sequence in Supabase")
    print("=" * 60)
    
    table_name = "hotpads_listings"
    
    try:
        print("\n1. Checking current maximum ID in hotpads_listings table...")
        max_id = get_max_id(table_name)
        total_records = get_total_records(table_name)
        print(f"   [OK] Current maximum ID: {max_id}")
        print(f"   [OK] Total records in table: {total_records}")
        
        next_sequence_value = max_id + 1
        print(f"\n2. Sequence should be set to: {next_sequence_value}")
        print(f"   (This ensures the next insert uses ID {next_sequence_value})")
        
        print("\n" + "=" * 70)
        print("SQL COMMAND TO FIX SEQUENCE")
        print("=" * 70)
        print("\nRun this SQL command in your Supabase SQL Editor:\n")
        print(f"SELECT setval('{table_name}_id_seq', {next_sequence_value}, false);")
        print("\n" + "=" * 70)
        
        print("\nSteps to fix:")
        print("1. Open your Supabase Dashboard")
        print("2. Go to SQL Editor")
        print("3. Paste the SQL command above")
        print("4. Click 'Run'")
        
        print(f"\nThis will reset the sequence to the correct value.")
        print(f"After this, new inserts will use IDs starting from {next_sequence_value}")
        
        print("\n[SUCCESS] Analysis complete!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("Please ensure your Supabase credentials are correct and the 'hotpads_listings' table exists.")

