from supabase import create_client, Client
import sys
import os
from pathlib import Path

# Add Scraper_backend to sys.path to import utils
backend_root = Path(__file__).resolve().parents[2]
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from utils.enrichment_manager import EnrichmentManager
from utils.placeholder_utils import is_placeholder_email

class HotpadsPipeline:
    def __init__(self):
        self.supabase: Client = None
        self.enrichment_manager = None
        self.items_buffer = []
        self.BATCH_SIZE = 1

    def open_spider(self, spider):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        
        spider.logger.info("=" * 60)
        if url and key:
            try:
                self.supabase = create_client(url, key)
                self.enrichment_manager = EnrichmentManager(self.supabase)
                # Test connection
                test = self.supabase.table("hotpads_listings").select("count", count="exact").limit(0).execute()
                spider.logger.info(f"SUPABASE: Connected successfully and initialized EnrichmentManager")
                spider.logger.info(f"SUPABASE: Current record count: {test.count}")
            except Exception as e:
                spider.logger.error(f"SUPABASE ERROR: Failed to connect or initialize EnrichmentManager - {e}")
                self.supabase = None
                self.enrichment_manager = None
        else:
            spider.logger.error("SUPABASE ERROR: Credentials missing in environment")
            spider.logger.error(f"  SUPABASE_URL: {'SET' if url else 'NOT SET'}")
            spider.logger.error(f"  SUPABASE_SERVICE_KEY: {'SET' if key else 'NOT SET'}")
        spider.logger.info("=" * 60)

    def close_spider(self, spider):
        if self.items_buffer:
            spider.logger.info(f"SUPABASE: Flushing final {len(self.items_buffer)} items...")
            self._flush_buffer(spider)
        
        # Final stats
        if self.supabase:
            try:
                final_count = self.supabase.table("hotpads_listings").select("count", count="exact").limit(0).execute()
                spider.logger.info("=" * 60)
                spider.logger.info(f"SUPABASE FINAL: Total records in database: {final_count.count}")
                spider.logger.info("=" * 60)
            except Exception as e:
                spider.logger.error(f"SUPABASE ERROR: Could not get final count - {e}")

    def process_item(self, item, spider):
        if not self.supabase:
            return item

        # Prepare data for Supabase - map old fields to new schema
        # Convert empty strings to None for numeric fields to avoid type errors
        def get_val(key):
            val = item.get(key)
            return val if val and str(val).strip() else None

        data = {
            "property_name": item.get("Name"),
            "contact_name": item.get("Contact Name"),
            "contact_company": item.get("Contact Company"),
            "email": item.get("Email"),
            "price": item.get("Price"),
            "bedrooms": get_val("Bedrooms"),
            "bathrooms": get_val("Bathrooms"),
            "square_feet": get_val("Sqft"),  # Fixed: was 'sqft', now 'square_feet'
            "address": item.get("Address"),
            "phone_number": item.get("Phone Number"),
            "url": item.get("Url"),
            "listing_date": item.get("Listing Time"),
        }
        
        self.items_buffer.append(data)
        
        # Immediate feedback for user
        spider.logger.info(f"✓ Scraped (Buffered): {data.get('property_name')} - {data.get('address')}")

        if len(self.items_buffer) >= self.BATCH_SIZE:
            self._flush_buffer(spider)

        return item

    def _flush_buffer(self, spider):
        if not self.items_buffer:
            return
            
        try:
            # Use upsert to handle duplicates gracefully (on_conflict='url')
            self.supabase.table("hotpads_listings").upsert(self.items_buffer, on_conflict="url").execute()
            spider.logger.info("=" * 60)
            spider.logger.info(f"SUPABASE BATCH SAVED: {len(self.items_buffer)} items written to database")
            
            # Enrichment Integration
            if self.enrichment_manager:
                for item_data in self.items_buffer:
                    try:
                        # Map Hotpads fields to generic enrichment fields
                        email = item_data.get("email")
                        if email and is_placeholder_email(email):
                            email = None  # Treat as missing
                            
                        enrichment_data = {
                            "address": item_data.get("address"),
                            "owner_name": item_data.get("contact_name"),
                            "owner_email": email,
                            "owner_phone": item_data.get("phone_number"),
                        }
                        address_hash = self.enrichment_manager.process_listing(enrichment_data, listing_source="Hotpads")
                        if address_hash:
                            # Update the item in the buffer with address_hash? 
                            # Better to update DB directly since we just flushed
                            self.supabase.table("hotpads_listings").update({"address_hash": address_hash}).eq("url", item_data.get("url")).execute()
                    except Exception as e:
                        spider.logger.error(f"ENRICHMENT ERROR: {e}")

            spider.logger.info("=" * 60)
            self.items_buffer = []
        except Exception as e:
            spider.logger.error("=" * 60)
            spider.logger.error(f"SUPABASE ERROR: Failed to save batch - {e}")
            spider.logger.error("=" * 60)
            # Keep buffer to try again? Or clear to avoid blocking? 
            # For now, clear to avoid memory issues if it's a persistent error, 
            # but in production you might want retry logic.
            self.items_buffer = []
