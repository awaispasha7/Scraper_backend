import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class OrphanCleanup:
    def __init__(self, dry_run=True):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        self.supabase: Client = create_client(url, key)
        self.dry_run = dry_run
        if self.dry_run:
            logger.info("🧪 DRY RUN MODE ENABLED")

    def run(self):
        logger.info(f"🚀 Starting Garbage Orphan Cleanup {'(DRY RUN)' if self.dry_run else ''}")
        
        # 1. Get all orphans
        res = self.supabase.table("property_owner_enrichment_state") \
            .select("id, address_hash, normalized_address") \
            .eq("status", "orphaned") \
            .execute()
        
        orphans = res.data or []
        logger.info(f"Found {len(orphans)} orphans to clean up.")
        
        if not orphans:
            logger.info("Nothing to clean.")
            return

        # 2. Delete them
        if not self.dry_run:
            orphan_ids = [o['id'] for o in orphans]
            # Delete in batches of 100
            batch_size = 100
            for i in range(0, len(orphan_ids), batch_size):
                batch = orphan_ids[i:i+batch_size]
                self.supabase.table("property_owner_enrichment_state").delete().in_("id", batch).execute()
                logger.info(f"Deleted batch of {len(batch)} orphans.")
        else:
            logger.info(f"  [DRY RUN] Would delete {len(orphans)} records.")
            if ImportError:
                # print sample
                for o in orphans[:3]:
                   logger.info(f"  Sample: {o.get('normalized_address')}")

        logger.info(f"✅ Cleanup Complete! {'(DRY RUN)' if self.dry_run else ''}")

if __name__ == "__main__":
    # Change to False to run for real
    cleanup = OrphanCleanup(dry_run=False)
    cleanup.run()
