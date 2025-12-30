import os
import sys
import hashlib
import logging
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Add shared utils
project_root = Path(__file__).resolve().parents[0]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address, generate_address_hash
from utils.sync_back_enriched import SyncBackEnriched

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

LISTING_TABLES = [
    {"table": "listings", "address_col": "address"},
    {"table": "zillow_fsbo_listings", "address_col": "address"},
    {"table": "zillow_frbo_listings", "address_col": "address"},
    {"table": "hotpads_listings", "address_col": "address"},
    {"table": "apartments_frbo_chicago", "address_col": "full_address"},
    {"table": "trulia_listings", "address_col": "address"},
    {"table": "redfin_listings", "address_col": "address"}
]

class ComprehensiveSupabaseRepair:
    def __init__(self, dry_run=True):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials missing.")
        self.supabase: Client = create_client(url, key)
        self.dry_run = dry_run
        if self.dry_run:
            logger.info("🧪 DRY RUN MODE ENABLED")

    def run(self):
        logger.info(f"🚀 Starting Comprehensive Supabase Repair {'(DRY RUN)' if self.dry_run else ''}")
        
        # 1. Standardize Listing Tables (Foundational)
        for config in LISTING_TABLES:
            self._standardize_listing_table(config)
            
        # 2. Repair Enrichment State & Link Property Owners
        self._repair_enrichment_and_owners()
        
        # 3. Final Sync-Back
        if not self.dry_run:
            logger.info("🔄 Triggering final sync-back...")
            syncer = SyncBackEnriched()
            syncer.run()
            
        logger.info(f"✅ Comprehensive Repair Complete! {'(DRY RUN)' if self.dry_run else ''}")

    def _standardize_listing_table(self, config):
        table = config['table']
        addr_col = config['address_col']
        logger.info(f"🧐 Standardizing {table} hashes...")
        
        page = 0
        while True:
            res = self.supabase.table(table).select(f"id, {addr_col}, address_hash").range(page*500, (page+1)*500 - 1).execute()
            rows = res.data
            if not rows: break
            
            for row in rows:
                raw_addr = row.get(addr_col)
                if not raw_addr: continue
                
                normalized = normalize_address(raw_addr)
                new_hash = generate_address_hash(normalized)
                old_hash = row.get('address_hash')
                
                if old_hash != new_hash:
                    if not self.dry_run:
                        self.supabase.table(table).update({"address_hash": new_hash}).eq("id", row['id']).execute()
                    else:
                        logger.info(f"  [DRY RUN] Would update hash in {table} for ID {row['id']}")
            
            if len(rows) < 500: break
            page += 1

    def _repair_enrichment_and_owners(self):
        logger.info("🧐 Standardizing Enrichment State & Owners Link...")
        page = 0
        while True:
            res = self.supabase.table("property_owner_enrichment_state").select("*").range(page*500, (page+1)*500 - 1).execute()
            rows = res.data
            if not rows: break
            
            for row in rows:
                raw_addr = row.get('original_address') or row.get('normalized_address')
                if not raw_addr: continue
                
                normalized = normalize_address(raw_addr)
                new_hash = generate_address_hash(normalized)
                old_hash = row['address_hash']
                
                # Calculate potential legacy MD5 (Raw)
                legacy_hash_raw = hashlib.md5(str(raw_addr).upper().strip().encode('utf-8')).hexdigest()
                # Calculate SHA256
                legacy_hash_sha256 = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
                
                possible_hashes = list(set([old_hash, legacy_hash_raw, legacy_hash_sha256]))
                
                # A. Update property_owners if they use any legacy hash
                for h in possible_hashes:
                    if h == new_hash: continue
                    owner_res = self.supabase.table("property_owners").select("id").eq("address_hash", h).execute()
                    if owner_res.data:
                        for owner in owner_res.data:
                            logger.info(f"🔗 Found owner record with legacy hash {h[:8]}. Updating to {new_hash[:8]}")
                            if not self.dry_run:
                                self.supabase.table("property_owners").update({"address_hash": new_hash}).eq("id", owner['id']).execute()
                            else:
                                logger.info(f"  [DRY RUN] Would update owner {owner['id']}")

                # B. Update enrichment state to standard hash
                if old_hash != new_hash:
                    logger.info(f"✨ Standardizing enrichment hash: {old_hash[:8]} -> {new_hash[:8]}")
                    if not self.dry_run:
                        try:
                            self.supabase.table("property_owner_enrichment_state").update({
                                "address_hash": new_hash,
                                "normalized_address": normalized
                            }).eq("id", row['id']).execute()
                        except Exception as e:
                            if "duplicate key" in str(e).lower():
                                logger.warning(f"  Collision for {new_hash[:8]}. Merging...")
                                self._merge_states(row, new_hash)
                            else:
                                logger.error(f"  Error: {e}")
                    else:
                        logger.info(f"  [DRY RUN] Would update enrichment record {row['id']}")

            if len(rows) < 500: break
            page += 1

    def _merge_states(self, duplicate_row: dict, target_hash: str):
        # Already implemented this logic in repair_hashes_and_sync.py but keeping here for completeness
        try:
            target_res = self.supabase.table("property_owner_enrichment_state").select("*").eq("address_hash", target_hash).maybe_single().execute()
            if not target_res.data: return
            target = target_res.data
            
            # Priority: enriched > failed > never_checked
            prio = {'enriched': 3, 'failed': 2, 'never_checked': 1, 'orphaned': 0}
            if prio.get(duplicate_row['status'], 0) > prio.get(target['status'], 0):
                self.supabase.table("property_owner_enrichment_state").update({"status": duplicate_row['status']}).eq("address_hash", target_hash).execute()
            
            self.supabase.table("property_owner_enrichment_state").delete().eq("id", duplicate_row['id']).execute()
        except: pass

if __name__ == "__main__":
    repair = ComprehensiveSupabaseRepair(dry_run=False) # Running in REAL mode as requested
    repair.run()
