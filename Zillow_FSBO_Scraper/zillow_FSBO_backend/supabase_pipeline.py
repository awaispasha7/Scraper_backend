import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from project root (Scraper_backend/.env)
project_root = Path(__file__).resolve().parents[2]  # Go up to Scraper_backend
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

class SupabasePipeline:
    def __init__(self):
        self.supabase: Client = None
        
    def open_spider(self, spider):
        """Initialize Supabase client when spider opens"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            spider.logger.error("Supabase credentials not found in environment variables")
            return
            
        self.supabase = create_client(url, key)
        spider.logger.info("Supabase client initialized successfully")
    
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
            
            # Upsert data (insert or update if exists based on detail_url)
            response = self.supabase.table("zillow_fsbo_listings").upsert(
                data,
                on_conflict="detail_url"
            ).execute()
            
            spider.logger.info(f"Successfully uploaded: {item.get('Address', 'Unknown')}")
            
        except Exception as e:
            spider.logger.error(f"Error uploading to Supabase: {e}")
            spider.logger.error(f"Item: {item}")
        
        return item
    
    def close_spider(self, spider):
        """Cleanup when spider closes"""
        spider.logger.info("Supabase pipeline closed")
