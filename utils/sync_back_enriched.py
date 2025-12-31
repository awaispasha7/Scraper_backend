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

    def run(self, status_filter="enriched"):
        logger.info(f"Starting sync-back of property data with status '{status_filter}'...")
        
        # 1. Get properties from enrichment state based on status
        state_res = self.supabase.table("property_owner_enrichment_state") \
            .select("address_hash, listing_source, status") \
            .eq("status", status_filter) \
            .execute()
        
        items = state_res.data or []
        logger.info(f"Found {len(items)} properties with '{status_filter}' status.")
        
        processed_count = 0
        success_count = 0
        
        for state in items:
            address_hash = state['address_hash']
            listing_source = state.get('listing_source')
            status = state.get('status')
            
            if not listing_source:
                continue
                
            try:
                if status == "enriched":
                    # Get the owner details from property_owners
                    owner_res = self.supabase.table("property_owners") \
                        .select("*") \
                        .eq("address_hash", address_hash) \
                        .execute()
                    
                    if owner_res.data:
                        self._sync_to_source(address_hash, listing_source, owner_res.data[0], "enriched")
                        success_count += 1
                elif status == "no_owner_data":
                    self._sync_to_source(address_hash, listing_source, {}, "no_owner_data")
                    success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to sync {address_hash[:8]} back to {listing_source}: {e}")
            
            processed_count += 1
            if processed_count % 50 == 0:
                logger.info(f"Processed {processed_count}/{len(items)}...")

        logger.info(f"Sync-back for '{status_filter}' complete. Successfully updated {success_count} source records.")

    def _sync_to_source(self, address_hash: str, listing_source: str, owner_data: dict, status: str):
        source_lower = listing_source.lower()
        target_table = self.source_map.get(source_lower)
        
        if not target_table:
            return

        update_payload = {
            "enrichment_status": status
        }

        if status == "enriched" and owner_data:
            # 1. Generic Owner Name (Most tables)
            if target_table == 'zillow_frbo_listings':
                update_payload["name"] = owner_data.get('owner_name')
            else:
                # Listings, zillow_fsbo, hotpads, apartments, trulia, redfin use owner_name
                update_payload["owner_name"] = owner_data.get('owner_name')
            
            # 2. Mailing Address (Only some tables)
            if target_table in ['listings', 'trulia_listings', 'redfin_listings']:
                update_payload["mailing_address"] = owner_data.get('mailing_address')

            # 3. Emails & Phones (Detailed Mapping)
            if target_table == 'listings':
                if owner_data.get('owner_email'):
                    update_payload["owner_emails"] = [owner_data.get('owner_email')]
                if owner_data.get('owner_phone'):
                    update_payload["owner_phones"] = [owner_data.get('owner_phone')]
            
            elif target_table in ['zillow_fsbo_listings', 'zillow_frbo_listings']:
                if owner_data.get('owner_email'):
                    update_payload["owner_email"] = owner_data.get('owner_email')
                if owner_data.get('owner_phone'):
                    update_payload["phone_number"] = owner_data.get('owner_phone')
            
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
        try:
            self.supabase.table(target_table).update(update_payload).eq("address_hash", address_hash).execute()
            logger.debug(f"Successfully updated {target_table} for {address_hash[:8]}")
        except Exception as e:
            error_str = str(e)
            if "enrichment_status" in update_payload:
                # Try again without enrichment_status
                logger.warning(f"Column 'enrichment_status' missing in {target_table}. Retrying without it.")
                del update_payload["enrichment_status"]
                try:
                    self.supabase.table(target_table).update(update_payload).eq("address_hash", address_hash).execute()
                    logger.debug(f"Successfully updated {target_table} (without status) for {address_hash[:8]}")
                except Exception as e2:
                    logger.error(f"Error updating {target_table} for {address_hash[:8]} even without status: {str(e2)}")
            else:
                logger.error(f"Error updating {target_table} for {address_hash[:8]}: {error_str}")

if __name__ == "__main__":
    syncer = SyncBackEnriched()
    # Try to sync enriched records first
    syncer.run(status_filter="enriched")
    # Then try to sync no_owner_data records
    # (Note: For no_owner_data, sync_back currently only updates status, 
    # so it will only work once the column is added)
    syncer.run(status_filter="no_owner_data")
