import os
import sys
import logging
from typing import List, Dict, Any, Set
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Add shared utils
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address, generate_address_hash
from utils.placeholder_utils import is_owner_data_complete

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

LISTING_TABLES = [
    {"table": "listings", "address_col": "address", "source": "ForSaleByOwner"},
    {"table": "zillow_fsbo_listings", "address_col": "address", "source": "Zillow FSBO"},
    {"table": "zillow_frbo_listings", "address_col": "address", "source": "Zillow FRBO"},
    {"table": "hotpads_listings", "address_col": "address", "source": "Hotpads"},
    {"table": "apartments_frbo_chicago", "address_col": "full_address", "source": "Apartments.com"},
    {"table": "trulia_listings", "address_col": "address", "source": "Trulia"},
    {"table": "redfin_listings", "address_col": "address", "source": "Redfin"}
]

class HashRepairMigration:
    def __init__(self, dry_run=True):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials missing.")
        self.supabase: Client = create_client(url, key)
        self.dry_run = dry_run
        if self.dry_run:
            logger.info("🧪 DRY RUN MODE ENABLED - No changes will be committed.")

    def run(self):
        logger.info(f"🚀 Starting Hash Standardization & Sync Repair Migration {'(DRY RUN)' if self.dry_run else ''}")
        
        # 1. Standardize property_owner_enrichment_state
        self._repair_enrichment_state()
        
        # 2. Standardize property_owners
        self._repair_property_owners()
        
        # 3. Standardize listing tables
        for config in LISTING_TABLES:
            self._repair_listing_table(config)
            
        # 4. Final Sync-Back
        if not self.dry_run:
            logger.info("🔄 Triggering final sync-back of enriched data...")
            from utils.sync_back_enriched import SyncBackEnriched
            syncer = SyncBackEnriched()
            syncer.run()
        else:
            logger.info("🧪 Skipping final sync-back in DRY RUN mode.")
        
        logger.info(f"✅ Migration & Sync Repair Complete! {'(DRY RUN)' if self.dry_run else ''}")

    def _repair_enrichment_state(self):
        logger.info("🧐 Standardizing property_owner_enrichment_state...")
        page = 0
        while True:
            res = self.supabase.table("property_owner_enrichment_state").select("*").range(page*500, (page+1)*500 - 1).execute()
            rows = res.data
            if not rows: break
            
            for row in rows:
                old_hash = row['address_hash']
                # ALWAYS re-normalize from original or normalized field to ensure true standard
                raw_addr = row.get('original_address') or row.get('normalized_address')
                if not raw_addr: continue
                
                normalized = normalize_address(raw_addr)
                new_hash = generate_address_hash(normalized)
                
                if old_hash != new_hash:
                    logger.info(f"  Fixing hash: {old_hash[:8]} -> {new_hash[:8]} ({normalized[:30]})")
                    try:
                        if not self.dry_run:
                            # Try to update
                            self.supabase.table("property_owner_enrichment_state").update({
                                "address_hash": new_hash,
                                "normalized_address": normalized
                            }).eq("id", row['id']).execute()
                        else:
                            logger.info(f"  [DRY RUN] Would update {row['id']} to {new_hash[:8]}")
                    except Exception as e:
                        if "duplicate key" in str(e).lower():
                            logger.warning(f"  Collision for {new_hash[:8]}. Merging...")
                            self._merge_enrichment_states(row, new_hash)
                        else:
                            logger.error(f"  Error updating {old_hash}: {e}")
            
            if len(rows) < 500: break
            page += 1

    def _merge_enrichment_states(self, duplicate_row: Dict, target_hash: str):
        """Handles collisions when a standardized hash already exists."""
        try:
            # 1. Fetch the existing record
            existing = self.supabase.table("property_owner_enrichment_state").select("*").eq("address_hash", target_hash).maybe_single().execute()
            if not existing.data: return
            
            target = existing.data
            
            # 2. Heuristic: Keep the more 'advanced' status
            status_priority = {'enriched': 4, 'no_owner_data': 3, 'failed': 2, 'never_checked': 1, 'orphaned': 0}
            target_prio = status_priority.get(target['status'], -1)
            dupe_prio = status_priority.get(duplicate_row['status'], -1)
            
            if dupe_prio > target_prio:
                # Update existing with better data
                logger.info(f"    Target {target_hash[:8]} has lower priority status '{target['status']}'. Updating with '{duplicate_row['status']}'.")
                if not self.dry_run:
                    self.supabase.table("property_owner_enrichment_state").update({
                        "status": duplicate_row['status'],
                        "listing_source": target['listing_source'] or duplicate_row['listing_source'],
                        "checked_at": target['checked_at'] or duplicate_row['checked_at'],
                        "source_used": target['source_used'] or duplicate_row['source_used']
                    }).eq("address_hash", target_hash).execute()
                else:
                    logger.info("    [DRY RUN] Would update existing record with better status.")
            
            # 3. Delete the duplicate row
            if not self.dry_run:
                self.supabase.table("property_owner_enrichment_state").delete().eq("id", duplicate_row['id']).execute()
                logger.info(f"    Deleted duplicate row {duplicate_row['id']}")
            else:
                logger.info(f"    [DRY RUN] Would delete duplicate row {duplicate_row['id']}")
            
        except Exception as e:
            logger.error(f"    Failed to merge {target_hash}: {e}")

    def _repair_property_owners(self):
        logger.info("🧐 Standardizing property_owners...")
        page = 0
        while True:
            res = self.supabase.table("property_owners").select("*").range(page*500, (page+1)*500 - 1).execute()
            rows = res.data
            if not rows: break
            
            for row in rows:
                old_hash = row['address_hash']
                # Try to get address from various sources
                # property_owners doesn't have original_address usually, but it has mailing_address
                # Wait, property_owners hash is USED to join with listing tables.
                # If we don't have the original property address here, we have a problem.
                # BUT, we can get it from enrichment_state if we join? 
                # Actually, many rows in property_owners ALREADY have 32-char hashes. 
                # Let's see if there are any non-standard ones.
                
                # If it's 64 chars, it's SHA256. We MUST fix those.
                if len(old_hash) == 64:
                    logger.warning(f"  Found SHA256 in property_owners: {old_hash[:8]}")
                    # Try to find the correct address from enrichment state or mailing address
                    # (This is rare, but let's be safe)
                    state = self.supabase.table("property_owner_enrichment_state").select("original_address, normalized_address").eq("address_hash", old_hash).maybe_single().execute()
                    if state.data:
                        normalized = state.data.get('normalized_address') or normalize_address(state.data['original_address'])
                        new_hash = generate_address_hash(normalized)
                        if new_hash:
                            try:
                                logger.info(f"    Updating property_owners hash: {old_hash[:8]} -> {new_hash[:8]}")
                                if not self.dry_run:
                                    self.supabase.table("property_owners").update({"address_hash": new_hash}).eq("address_hash", old_hash).execute()
                                else:
                                    logger.info(f"    [DRY RUN] Would update property_owners hash.")
                            except Exception as e:
                                logger.error(f"    Failed to update owner {old_hash}: {e}")
                
                # If it's MD5 but was raw instead of normalized? 
                # This is harder to check without the original address.
                # For now, focus on SHA256 corrections and rely on listing tables repair + sync-back.
            
            if len(rows) < 500: break
            page += 1

    def _repair_listing_table(self, config):
        table = config['table']
        addr_col = config['address_col']
        logger.info(f"🧐 Standardizing listing table: {table}...")
        
        page = 0
        while True:
            res = self.supabase.table(table).select(f"id, {addr_col}, address_hash").range(page*500, (page+1)*500 - 1).execute()
            rows = res.data
            if not rows: break
            
            for row in rows:
                old_hash = row.get('address_hash')
                raw_addr = row.get(addr_col)
                if not raw_addr: continue
                
                normalized = normalize_address(raw_addr)
                new_hash = generate_address_hash(normalized)
                
                if old_hash != new_hash:
                    # Update the hash
                    try:
                        logger.info(f"  Fixing hash in {table}: {old_hash} -> {new_hash[:8]}... (ID: {row['id']})")
                        if not self.dry_run:
                            self.supabase.table(table).update({"address_hash": new_hash}).eq("id", row['id']).execute()
                        else:
                            logger.info(f"  [DRY RUN] Would update {table} ID {row['id']}")
                    except Exception as e:
                        logger.error(f"  Failed update in {table} for ID {row['id']}: {e}")
            
            if len(rows) < 500: break
            page += 1

if __name__ == "__main__":
    migration = HashRepairMigration()
    migration.run()
