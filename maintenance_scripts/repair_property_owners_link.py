import os
import json
import logging
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Add shared utils
project_root = Path(__file__).resolve().parents[0]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address, generate_address_hash

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class PropertyOwnersLinkRepair:
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
        logger.info(f"🚀 Starting Property Owners Link Repair {'(DRY RUN)' if self.dry_run else ''}")
        
        # 1. Load the pre-migration dump
        dump_path = Path("orphans_dump.json")
        if not dump_path.exists():
            logger.error("❌ orphans_dump.json not found! Cannot proceed with mapping.")
            return
            
        with open(dump_path, 'r') as f:
            orphans = json.load(f)
            
        logger.info(f"📋 Loaded {len(orphans)} orphans from dump.")
        
        repaired_count = 0
        for orphan in orphans:
            old_hash = orphan['address_hash']
            raw_addr = orphan.get('normalized_address') # In the dump, this was actually the raw address
            if not raw_addr: continue
            
            # Calculate what the NEW hash is
            normalized = normalize_address(raw_addr)
            new_hash = generate_address_hash(normalized)
            
            if old_hash == new_hash:
                continue # Already correct (or was already normalized)
                
            # Check if this old_hash exists in property_owners
            owner_res = self.supabase.table("property_owners").select("id, owner_name").eq("address_hash", old_hash).execute()
            if owner_res.data:
                for owner in owner_res.data:
                    logger.info(f"🔗 Found owner record for {owner['owner_name']} with old hash {old_hash[:8]}. Mapping to {new_hash[:8]}")
                    
                    if not self.dry_run:
                        # Update property_owners hash
                        try:
                            self.supabase.table("property_owners").update({"address_hash": new_hash}).eq("id", owner['id']).execute()
                            
                            # Also update enrichment state status if it was 'orphaned' but now we found the owner
                            state_res = self.supabase.table("property_owner_enrichment_state").select("id, status").eq("address_hash", new_hash).maybe_single().execute()
                            if state_res.data:
                                current_status = state_res.data['status']
                                if current_status in ['never_checked', 'orphaned']:
                                    logger.info(f"  ✨ Updating enrichment status for {new_hash[:8]} to 'enriched'")
                                    self.supabase.table("property_owner_enrichment_state").update({
                                        "status": "enriched",
                                        "listing_source": orphan.get('listing_source') or state_res.data.get('listing_source')
                                    }).eq("id", state_res.data['id']).execute()
                        except Exception as e:
                            logger.error(f"  ❌ Error updating link: {e}")
                    else:
                        logger.info(f"  [DRY RUN] Would update owner {owner['id']} and potentially enrichment status.")
                    
                    repaired_count += 1

        logger.info(f"✅ Repaired {repaired_count} owner links. {'(DRY RUN)' if self.dry_run else ''}")
        
        if not self.dry_run and repaired_count > 0:
            logger.info("🔄 Triggering final sync-back...")
            from utils.sync_back_enriched import SyncBackEnriched
            syncer = SyncBackEnriched()
            syncer.run()

if __name__ == "__main__":
    repair = PropertyOwnersLinkRepair(dry_run=False) # Run directly in real mode since we matched Fairside
    repair.run()
