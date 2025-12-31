from supabase import create_client, Client
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add Scraper_backend to sys.path to import utils
backend_root = Path(__file__).resolve().parents[2]
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from utils.enrichment_manager import EnrichmentManager

# Load environment variables from project root (Scraper_backend/.env)
project_root = Path(__file__).resolve().parents[2]  # Go up to Scraper_backend
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

class SupabasePipeline:
    def __init__(self):
        self.supabase: Client = None
        self.enrichment_manager = None
        
    def open_spider(self, spider):
        """Initialize Supabase client when spider opens"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            spider.logger.error("Supabase credentials not found in environment variables")
            return
            
        self.supabase = create_client(url, key)
        self.enrichment_manager = EnrichmentManager(self.supabase)
        spider.logger.info("Supabase client and EnrichmentManager initialized successfully")
    
    def process_item(self, item, spider):
        """Upload item to Supabase"""
        if not self.supabase:
            spider.logger.warning("Supabase client not initialized, skipping item")
            return item
        
        try:
            # Prepare data for Supabase (convert field names to snake_case)
            data = {
                "detail_url": item.get("Detail_URL", ""),
                "address": item.get("Address", ""),
                "bedrooms": item.get("Bedrooms", ""),
                "bathrooms": item.get("Bathrooms", ""),
                "price": item.get("Price", ""),
                "home_type": item.get("Home_Type", ""),
                "year_build": item.get("Year_Build", ""),
                "hoa": item.get("HOA", ""),
                "days_on_zillow": item.get("Days_On_Zillow", ""),
                "page_view_count": item.get("Page_View_Count", ""),
                "favorite_count": item.get("Favorite_Count", ""),
                "phone_number": item.get("Phone_Number", ""),
            }
            
            # Actually upsert the data to Supabase
            self.supabase.table("zillow_fsbo_listings").upsert(data, on_conflict="detail_url").execute()
            
            spider.logger.info(f"Successfully uploaded: {item.get('Address', 'Unknown')}")
            
            # Enrichment Integration
            if self.enrichment_manager:
                try:
                    enrichment_data = {
                        "address": item.get("Address"),
                        "owner_name": None, # Zillow FSBO often doesn't give name in search results
                        "owner_email": None,
                        "owner_phone": item.get("Phone_Number"),
                    }
                    address_hash = self.enrichment_manager.process_listing(enrichment_data, listing_source="Zillow FSBO")
                    if address_hash:
                        self.supabase.table("zillow_fsbo_listings").update({"address_hash": address_hash}).eq("detail_url", item.get("Detail_URL")).execute()
                except Exception as e:
                    spider.logger.error(f"ENRICHMENT ERROR: {e}")
            
        except Exception as e:
            spider.logger.error(f"Error uploading to Supabase: {e}")
            spider.logger.error(f"Item: {item}")
        
        return item
    
    def close_spider(self, spider):
        """Cleanup when spider closes"""
        spider.logger.info("Supabase pipeline closed")
