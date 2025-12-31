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
if not env_path.exists():
    # Fallback to current directory for safety
    env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger(__name__)


class SupabasePipeline:
    """
    Scrapy pipeline to store scraped items in Supabase database
    """
    
    def __init__(self):
        self.supabase: Client = None
        self.enrichment_manager = None
        self.table_name = "trulia_listings"
        self.uploaded_count = 0
        self.error_count = 0
        
    def open_spider(self, spider):
        """Initialize Supabase client when spider opens"""
        try:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")
            
            self.supabase = create_client(url, key)
            self.enrichment_manager = EnrichmentManager(self.supabase)
            logger.info(f"[OK] Connected to Supabase and initialized EnrichmentManager")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to Supabase: {e}")
            self.supabase = None
    
    def parse_beds_baths(self, beds_baths_str):
        """Parse '2 Beds 1.5 Baths' into separate beds and baths values"""
        if not beds_baths_str or beds_baths_str.strip() == '':
            return None, None
        
        # Extract beds
        beds_match = re.search(r'(\d+(?:\.\d+)?)\s*Bed', str(beds_baths_str), re.IGNORECASE)
        beds = beds_match.group(1) if beds_match else None
        
        # Extract baths
        baths_match = re.search(r'(\d+(?:\.\d+)?)\s*Bath', str(beds_baths_str), re.IGNORECASE)
        baths = baths_match.group(1) if baths_match else None
        
        return beds, baths
    
    def clean_value(self, value):
        """Clean values - handle empty strings, 'no data', etc."""
        if not value or (isinstance(value, str) and value.strip() == '') or str(value).strip().lower() == 'no data':
            return None
        return str(value).strip() if value else None
    
    def process_item(self, item, spider):
        """Process and insert/update item in Supabase"""
        if not self.supabase:
            logger.warning("Supabase client not initialized, skipping item")
            return item
        
        try:
            # Convert item to dict if needed
            item_dict = dict(item) if not isinstance(item, dict) else item
            
            # Get listing link (URL)
            listing_link = self.clean_value(item_dict.get("Url", ""))
            if not listing_link:
                logger.warning(f"Skipping item - missing URL: {item_dict.get('Address', 'Unknown')}")
                return item
            
            # Get address
            address = self.clean_value(item_dict.get("Address", ""))
            if not address:
                logger.warning(f"Skipping item - missing Address: {listing_link}")
                return item
            
            # Parse beds and baths from "Beds / Baths" column
            beds_baths_str = self.clean_value(item_dict.get("Beds / Baths", ""))
            beds, baths = self.parse_beds_baths(beds_baths_str) if beds_baths_str else (None, None)
            
            # Prepare data for Supabase trulia_listings table
            data = {
                "listing_link": listing_link,
                "address": address,
                "price": self.clean_value(item_dict.get("Asking Price", "")),
                "beds": beds,
                "baths": baths,
                "owner_name": self.clean_value(item_dict.get("Name", "")),  # Owner name from spider
                "phones": self.clean_value(item_dict.get("Phone Number", "")),
                "emails": None,  # Not available from spider
                "mailing_address": None,  # Not available from spider
                "square_feet": None,  # Will be updated later if available
                "property_type": None,  # Not available from spider
                "lot_size": None,  # Not available from spider
                "description": None,  # Not available from spider
                "scrape_date": datetime.now().strftime('%Y-%m-%d'),
            }
            
            # Remove None values (but keep empty strings for required fields)
            data = {k: v for k, v in data.items() if v is not None}
            
            # Actually upsert the data to Supabase
            self.supabase.table(self.table_name).upsert(data, on_conflict="listing_link").execute()
            
            self.uploaded_count += 1
            logger.info(f"[OK] Saved to Supabase: {address[:50]}... | Price: {data.get('price', 'N/A')} | Beds: {beds or 'N/A'} | Baths: {baths or 'N/A'}")
            
            # Enrichment Integration
            if self.enrichment_manager:
                try:
                    enrichment_data = {
                        "address": address,
                        "owner_name": data.get("owner_name"),
                        "owner_email": None,
                        "owner_phone": data.get("phones"),
                    }
                    address_hash = self.enrichment_manager.process_listing(enrichment_data, listing_source="Trulia")
                    if address_hash:
                        self.supabase.table(self.table_name).update({"address_hash": address_hash}).eq("listing_link", data.get("listing_link")).execute()
                except Exception as e:
                    logger.error(f"[ERROR] ENRICHMENT ERROR: {e}")
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"[ERROR] Failed to save item to Supabase: {e}")
            logger.error(f"   Item: {item_dict.get('Address', 'Unknown')}")
            logger.error(f"   URL: {item_dict.get('Url', 'N/A')}")
        
        return item
    
    def close_spider(self, spider):
        """Cleanup when spider closes"""
        logger.info(f"Closing Supabase pipeline")
        logger.info(f"Total uploaded: {self.uploaded_count} | Errors: {self.error_count}")
