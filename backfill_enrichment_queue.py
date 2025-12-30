import os
import sys
import re
import logging
from typing import List, Dict, Set
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Add shared utils
project_root = Path(__file__).resolve().parents[0]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address, generate_address_hash
from utils.placeholder_utils import clean_owner_data, is_owner_data_complete

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Silence verbose HTTP logs from Supabase client
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

load_dotenv()

# Configuration for all 7 listing tables
# We track owner_cols only to see if we can "scrape" data ourselves, 
# but for Zillow/Hotpads/Apartments, we generally ASSUME incomplete 
# unless property_owners has it.
LISTING_TABLES = [
    {
        "table": "listings", # ForSaleByOwner.com
        "address_col": "address",
        "source": "ForSaleByOwner",
        "owner_cols": ["owner_name", "owner_emails", "owner_phones"]
    },
    {
        "table": "zillow_fsbo_listings",
        "address_col": "address",
        "source": "Zillow FSBO",
        "owner_cols": ["owner_name", "owner_email", "phone_numbers"]
    },
    {
        "table": "zillow_frbo_listings",
        "address_col": "address",
        "source": "Zillow FRBO",
        "owner_cols": ["name", "owner_email", "phone_number"] # name is owner_name
    },
    {
        "table": "hotpads_listings",
        "address_col": "address",
        "source": "Hotpads",
        "owner_cols": ["contact_name", "url", "phone_number"] # email is often placeholder, check contact_name/phone
    },
    {
        "table": "apartments_frbo_chicago",
        "address_col": "full_address", # Or title? full_address seems better
        "source": "Apartments.com",
        "owner_cols": ["owner_name", "owner_email", "phone_numbers"]
    },
    {
        "table": "trulia_listings",
        "address_col": "address",
        "source": "Trulia",
        "owner_cols": ["owner_name", "emails", "phones"]
    },
    {
        "table": "redfin_listings",
        "address_col": "address",
        "source": "Redfin",
        "owner_cols": ["owner_name", "emails", "phones"]
    }
]

def map_listing_cols(table_config, listing):
    """Maps varied column names to standard owner fields."""
    cols = table_config['owner_cols']
    
    # Generic mapping
    # 0: name, 1: email, 2: phone
    # Some tables might have different order or names, let's be robust
    
    name = listing.get(cols[0]) if len(cols) > 0 else None
    
    # Special handling for tables where index 1 might not be email or index 2 phone
    email = None
    phone = None
    
    if len(cols) > 1:
        val = listing.get(cols[1])
        # Heuristic: if it looks like email/list of emails
        email = val
        
    if len(cols) > 2:
        val = listing.get(cols[2])
        phone = val
        
    # Specific overrides based on known schemas
    if table_config['table'] == 'hotpads_listings':
        if 'owner_name' in listing: name = listing.get('owner_name')
        if 'owner_phone' in listing: phone = listing.get('owner_phone')
        # email is unreliable in hotpads (support@hotpads.com)
        
    return name, email, phone

def backfill_enrichment_queue():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.error("Supabase credentials missing.")
        return

    supabase: Client = create_client(url, key)

    # 1. Fetch current enrichment state to avoid duplicates
    # We want to know if they exist at all.
    logger.info("Fetching existing enrichment state...")
    existing_state_hashes = set()
    page = 0
    while True:
        res = supabase.table("property_owner_enrichment_state").select("address_hash").range(page*1000, (page+1)*1000 - 1).execute()
        rows = res.data
        if not rows: break
        for r in rows: existing_state_hashes.add(r['address_hash'])
        page += 1
        if len(rows) < 1000: break
    
    logger.info(f"Found {len(existing_state_hashes)} existing records in enrichment state.")

    # 2. Fetch property_owners to check if we already have data (possibly from other sources)
    # If we have complete data there, we don't need to queue.
    # CRITICAL: We now check mailing_address too!
    logger.info("Fetching property_owners completeness data...")
    property_owners_complete = set()
    page = 0
    while True:
        res = supabase.table("property_owners").select("address_hash, owner_name, owner_email, owner_phone, mailing_address").range(page*1000, (page+1)*1000 - 1).execute()
        rows = res.data
        if not rows: break
        for r in rows:
            is_complete, _ = is_owner_data_complete(r.get('owner_name'), r.get('owner_email'), r.get('owner_phone'), r.get('mailing_address'))
            if is_complete:
                property_owners_complete.add(r['address_hash'])
        page += 1
        if len(rows) < 1000: break
    
    logger.info(f"Found {len(property_owners_complete)} records with COMPLETE data in property_owners.")

    # 3. Iterate through all listing tables
    total_queued = 0
    
    for config in LISTING_TABLES:
        table_name = config['table']
        source = config['source']
        logger.info(f"Processing table: {table_name}...")
        
        # Paginate through listings
        page = 0
        while True:
            try:
                # Select address + owner columns
                cols_to_fetch = [config['address_col']] + config['owner_cols']
                res = supabase.table(table_name).select("*").range(page*1000, (page+1)*1000 - 1).execute()
                listings = res.data
                
                if not listings: break
                
                batch_to_insert = []
                
                for listing in listings:
                    raw_addr = listing.get(config['address_col'])
                    if not raw_addr: continue
                    
                    normalized = normalize_address(raw_addr)
                    address_hash = generate_address_hash(normalized)
                    
                    # REQUIREMENT C: Ensure address_hash is consistent across all listing tables
                    # We must backfill the address_hash to the source table if it's missing/different
                    # We do this update regardless of queueing to ensure frontend joins work.
                    current_hash = listing.get('address_hash')
                    if current_hash != address_hash:
                         try:
                             # Efficiently update just this row? 
                             # Or maybe do it in bulk if many are missing? 
                             # For simplicity and safety in this script, we update individually or could batch.
                             # Given Supabase Python client limits, individual updates might be slow but safe.
                             # Let's try to update. assuming primary key?
                             # Most tables don't have a clean single PK we grabbed.
                             # We grabbed '*' so maybe we have 'id'.
                             if 'id' in listing:
                                 supabase.table(table_name).update({"address_hash": address_hash}).eq("id", listing['id']).execute()
                             elif config['table'] == 'hotpads_listings':
                                 # Hotpads uses url as PK often?
                                 if 'url' in listing:
                                     supabase.table(table_name).update({"address_hash": address_hash}).eq("url", listing['url']).execute()
                         except Exception as e:
                             logger.warning(f"Failed to backfill hash for {table_name} row: {e}")

                    # CHECK 1: Is it already in enrichment state?
                    if address_hash in existing_state_hashes:
                        # Ensure original_address is populated if missing
                        try:
                            supabase.table("property_owner_enrichment_state").update({"original_address": raw_addr}).eq("address_hash", address_hash).is_("original_address", "null").execute()
                        except: pass
                        continue
                        
                    # CHECK 2: Do we already have complete data (including mailing) in property_owners?
                    if address_hash in property_owners_complete:
                         continue
                         
                    # Determine missing fields (just for metadata, though property_owners check is authoritative)
                    # We can use the listing data to populate missing fields calc, just so we know what's there
                    name, email, phone = map_listing_cols(config, listing)
                    _, missing = is_owner_data_complete(name, email, phone, None) # mailing always missing in listing table usually
                    
                    # If we are here, we need enrichment.
                    batch_to_insert.append({
                        "address_hash": address_hash,
                        "normalized_address": normalized,
                        "original_address": raw_addr,
                        "status": "never_checked",
                        "locked": False,
                        "listing_source": source,
                        "missing_fields": missing
                    })
                    
                    # Update local set so we don't double queue duplicates in same run
                    existing_state_hashes.add(address_hash)

                if batch_to_insert:
                    try:
                        # Upsert to enrichment state
                        # on_conflict="address_hash" should handle dupes, but we wrap in try just in case
                        supabase.table("property_owner_enrichment_state").upsert(batch_to_insert, on_conflict="address_hash").execute()
                        total_queued += len(batch_to_insert)
                        logger.info(f"  Queued {len(batch_to_insert)} items from {table_name} (Page {page})")
                    except Exception as e:
                        logger.error(f"  Error inserting batch for {table_name}: {e}")
                        # Optionally try one by one if batch fails? For now just log.

                page += 1
                if len(listings) < 1000: break
                
            except Exception as e:
                logger.error(f"Error processing {table_name} page {page}: {e}")
                # Don't break, try next page/table?
                # If page fails, maybe next page works.
                page += 1 
                continue

    logger.info(f"Backfill complete. Total new items queued: {total_queued}")

if __name__ == "__main__":
    backfill_enrichment_queue()
