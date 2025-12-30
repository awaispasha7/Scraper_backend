import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class SyncBackEnriched:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials missing.")
        self.supabase: Client = create_client(url, key)
        
        # Mapping from source string to table name
        self.source_map = {
            'fsbo': 'listings',
            'forsalebyowner': 'listings',
            'zillow-fsbo': 'zillow_fsbo_listings',
            'zillow fsbo': 'zillow_fsbo_listings',
            'zillow-frbo': 'zillow_frbo_listings',
            'zillow frbo': 'zillow_frbo_listings',
            'hotpads': 'hotpads_listings',
            'apartments': 'apartments_frbo_chicago',
            'apartments.com': 'apartments_frbo_chicago',
            'trulia': 'trulia_listings',
            'redfin': 'redfin_listings'
        }

    def run(self):
        logger.info("Starting sync-back of existing enriched properties...")
        
        # 1. Get all enriched properties from enrichment state
        # We also need the listing_source from this table
        state_res = self.supabase.table("property_owner_enrichment_state") \
            .select("address_hash, listing_source") \
            .eq("status", "enriched") \
            .execute()
        
        enriched_states = state_res.data or []
        logger.info(f"Found {len(enriched_states)} properties with 'enriched' status.")
        
        processed_count = 0
        success_count = 0
        
        for state in enriched_states:
            address_hash = state['address_hash']
            listing_source = state.get('listing_source')
            
            if not listing_source:
                logger.warning(f"No listing_source for {address_hash[:8]}, skipping.")
                continue
                
            # 2. Get the owner details from property_owners
            owner_res = self.supabase.table("property_owners") \
                .select("*") \
                .eq("address_hash", address_hash) \
                .execute()
            
            if not owner_res.data:
                logger.warning(f"No data found in property_owners for {address_hash[:8]}, skipping.")
                continue
                
            owner_data = owner_res.data[0]
            
            # 3. Sync back to correct table
            try:
                self._sync_to_source(address_hash, listing_source, owner_data)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to sync {address_hash[:8]} back to {listing_source}: {e}")
            
            processed_count += 1
            if processed_count % 10 == 0:
                logger.info(f"Processed {processed_count}/{len(enriched_states)}...")

        logger.info(f"Sync-back complete. Successfully updated {success_count} source records.")

    def _sync_to_source(self, address_hash: str, listing_source: str, owner_data: dict):
        source_lower = listing_source.lower()
        target_table = self.source_map.get(source_lower)
        
        if not target_table:
            logger.debug(f"Source '{listing_source}' not in map, cannot sync back.")
            return

        update_payload = {
            "owner_name": owner_data.get('owner_name')
        }
        
        # Table-specific column mapping
        if target_table in ['listings', 'trulia_listings', 'redfin_listings']:
            update_payload["mailing_address"] = owner_data.get('mailing_address')

        if target_table == 'listings':
            if owner_data.get('owner_email'):
                update_payload["owner_emails"] = [owner_data.get('owner_email')]
            if owner_data.get('owner_phone'):
                update_payload["owner_phones"] = [owner_data.get('owner_phone')]
        
        elif target_table in ['zillow_fsbo_listings', 'zillow_frbo_listings']:
            if owner_data.get('owner_phone'):
                update_payload["phone_number"] = owner_data.get('owner_phone')
            if owner_data.get('owner_email'):
                update_payload["owner_email"] = owner_data.get('owner_email')
        
        elif target_table == 'apartments_frbo_chicago':
            if owner_data.get('owner_email'):
                update_payload["owner_email"] = owner_data.get('owner_email')
            if owner_data.get('owner_phone'):
                update_payload["phone_numbers"] = [owner_data.get('owner_phone')]
        
        elif target_table == 'hotpads_listings':
            if owner_data.get('owner_email'):
                update_payload["email"] = owner_data.get('owner_email')
            if owner_data.get('owner_phone'):
                update_payload["owner_phone"] = owner_data.get('owner_phone')
                update_payload["phone_number"] = owner_data.get('owner_phone')

        elif target_table in ['trulia_listings', 'redfin_listings']:
            if owner_data.get('owner_email'):
                update_payload["emails"] = owner_data.get('owner_email')
            if owner_data.get('owner_phone'):
                update_payload["phones"] = owner_data.get('owner_phone')

        # Run update
        self.supabase.table(target_table).update(update_payload).eq("address_hash", address_hash).execute()
        logger.debug(f"Updated {target_table} for {address_hash[:8]}")

if __name__ == "__main__":
    syncer = SyncBackEnriched()
    syncer.run()
