import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).resolve().parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

def setup_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return

    supabase: Client = create_client(url, key)
    print("Connected to Supabase.")

    # 1. Create scrape_state table
    # Since we can't run arbitrary SQL via the library easily without a custom endpoint or RPC,
    # we will use the table creation via the dashboard as a recommendation, 
    # but we can try to initialize the table by inserting a dummy record if it fails to select.
    
    print("Checking for scrape_state table...")
    try:
        supabase.table("scrape_state").select("*").limit(1).execute()
        print("scrape_state table already exists.")
    except Exception:
        print("Note: If scrape_state table doesn't exist, please create it in the Supabase Dashboard:")
        print("""
        CREATE TABLE scrape_state (
            source_site TEXT PRIMARY KEY,
            last_scraped_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen_id TEXT,
            last_seen_url TEXT,
            config JSONB DEFAULT '{}'::jsonb
        );
        """)

    # 2. Ensure Unique Constraints
    # This is critical for 'upsert' to work correctly.
    # The current pipelines already use 'upsert', so they likely have these constraints.
    tables = [
        "zillow_fsbo_listings",
        "zillow_frbo_listings",
        "hotpads_listings",
        "redfin_listings",
        "trulia_listings",
        "apartments_listings",
        "fsbo_listings"
    ]
    
    print("\nListing tables should have UNIQUE constraints on 'url' or 'detail_url'.")
    print("Typical command: ALTER TABLE table_name ADD CONSTRAINT unique_url UNIQUE (url);")

if __name__ == "__main__":
    setup_supabase()
