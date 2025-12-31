from supabase import create_client, Client
from dotenv import load_dotenv
import sys

# Add Scraper_backend to sys.path to import utils
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from utils.enrichment_manager import EnrichmentManager

# Load environment variables from project root (Scraper_backend/.env)
project_root = Path(__file__).resolve().parents[3]  # Go up to Scraper_backend
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class SupabasePipeline:
    """
    Scrapy pipeline to store scraped items in Supabase database
    """
    
    def __init__(self):
        self.supabase: Client = None
        self.enrichment_manager = None
        self.table_name = "zillow_frbo_listings"
        
    def open_spider(self, spider):
        """Initialize Supabase client when spider opens"""
        try:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")
            
            self.supabase = create_client(url, key)
            self.enrichment_manager = EnrichmentManager(self.supabase)
            logger.info(f"✅ Connected to Supabase and initialized EnrichmentManager")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Supabase: {e}")
            self.supabase = None
    
    def close_spider(self, spider):
        """Cleanup when spider closes"""
        logger.info(f"🔒 Closing Supabase pipeline")
    
    def process_item(self, item, spider):
        """Process and insert/update item in Supabase"""
        if not self.supabase:
            logger.warning("⚠️ Supabase client not initialized, skipping item")
            return item
        
        try:
            # Convert item to dict if needed
            item_dict = dict(item) if not isinstance(item, dict) else item
            
            # Prepare data for Supabase - Note: spider uses capitalized field names
            data = {
                "url": item_dict.get("Url", ""),
                "zpid": str(item_dict.get("zpid", "")),  # Convert to string
                "address": item_dict.get("Address", ""),
                "city": item_dict.get("City", ""),  # May not be in spider
                "state": item_dict.get("State", ""),  # May not be in spider
                "zipcode": item_dict.get("Zip", ""),  # May not be in spider
                "asking_price": item_dict.get("Asking Price", ""),
                "beds_baths": item_dict.get("Beds / Baths", ""),
                "year_built": str(item_dict.get("YearBuilt", "")) if item_dict.get("YearBuilt") else None,
                "name": item_dict.get("Name", ""),
                "phone_number": item_dict.get("Phone Number", ""),
                "agent_name": item_dict.get("Agent Name", ""),
            }
            

            # Remove None and empty string values
            data = {k: v for k, v in data.items() if v is not None and v != ""}
            
            # Ensure required fields are present
            if not data.get("url"):
                logger.warning(f"⚠️ Skipping item - missing URL: {item_dict}")
                return item
                
            # CRITICAL FIX: Skip items with no address (Ghost Listings)
            if not data.get("address"):
                logger.warning(f"👻 Skipping Ghost Listing (No Address): {data.get('url')}")
                return item
            
            # Actually upsert the data to Supabase
            self.supabase.table(self.table_name).upsert(data, on_conflict="url").execute()
            
            logger.info(f"✅ Saved to Supabase: {data.get('address', 'Unknown')} (ZPID: {data.get('zpid', 'N/A')})")
            
            # Enrichment Integration
            if self.enrichment_manager:
                try:
                    enrichment_data = {
                        "address": data.get("address"),
                        "owner_name": data.get("name"),
                        "owner_email": None,
                        "owner_phone": data.get("phone_number"),
                    }
                    address_hash = self.enrichment_manager.process_listing(enrichment_data, listing_source="Zillow FRBO")
                    if address_hash:
                        self.supabase.table(self.table_name).update({"address_hash": address_hash}).eq("url", data.get("url")).execute()
                except Exception as e:
                    logger.error(f"❌ ENRICHMENT ERROR: {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save item to Supabase: {e}")
            logger.error(f"   Item: {item_dict.get('Address', 'Unknown')}")
            logger.error(f"   Data prepared: {data if 'data' in locals() else 'Failed before data prep'}")
        
        return item
