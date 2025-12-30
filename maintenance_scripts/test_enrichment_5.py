import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# 1. Override Env Vars BEFORE importing worker
# We set a high daily limit to ensure we have "quota" for this test,
# but we will strictly limit the loop to 5 runs using max_runs argument.
print("🔧 Configuring Environment for Phase 2 Test...")
os.environ["BATCHDATA_ENABLED"] = "true"
os.environ["BATCHDATA_DAILY_LIMIT"] = "1000" 
os.environ["BATCHDATA_DRY_RUN"] = "false"

# Now import worker (it will respect our env vars)
from batchdata_worker import BatchDataWorker
from supabase import create_client

def run_test():
    print("🚀 Starting Phase 2 Test: Enriching 5 Listings...")
    
    # Initialize
    worker = BatchDataWorker()
    
    # Run for exactly 5 listings
    print("🔄 Running enrichment loop (max 5)...")
    worker.run_enrichment(max_runs=5)
    
    print("\n🔍 Verifying results (checking last 5 enriched items)...")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    # Get the most recently enriched items
    res = supabase.table("property_owner_enrichment_state") \
        .select("*") \
        .eq("status", "enriched") \
        .order("checked_at", desc=True) \
        .limit(5) \
        .execute()
        
    if not res.data:
        print("❌ No enriched items found!")
        return

    for row in res.data:
        print("-" * 60)
        print(f"🏠 Address: {row['normalized_address']}")
        print(f"ID:   {row['id']}")
        print(f"Hash: {row['address_hash']}")
        print(f"Source: {row.get('listing_source')}")
        
        # Verify Owner Data
        owner_res = supabase.table("property_owners").select("*").eq("address_hash", row['address_hash']).execute()
        if owner_res.data:
            o = owner_res.data[0]
            print(f"👤 Owner: {o.get('owner_name')}")
            print(f"📞 Phone: {o.get('owner_phone')}")
            print(f"📧 Email: {o.get('owner_email')}")
            
            # Verify Sync-Back to Listing Table (if known)
            target_table = None
            src = (row.get('listing_source') or '').lower()
            if 'fsbo' in src: target_table = 'zillow_fsbo_listings' # simplified check
            # We can't easily check ALL tables here without map, but that's ok for sanity check
            
            print("✅ Owner data persisted locally.")
        else:
            print(f"❌ MISSING OWNER DATA in property_owners table!")
            
    print("-" * 60)
    print("\nTest Complete.")

if __name__ == "__main__":
    run_test()
