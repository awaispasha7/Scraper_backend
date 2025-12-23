# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import csv
import os
import re
from datetime import datetime
from pathlib import Path
from itemadapter import ItemAdapter
from dotenv import load_dotenv

# Try to import supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class RedfinScraperPipeline:
    def __init__(self):
        self.items = []
        self.csv_file = None
        self.writer = None
        self.supabase = None
        self.fieldnames = [
            'Name',
            'Beds / Baths',
            'Phone Number',
            'Asking Price',
            'Days On Redfin',
            'Address',
            'YearBuilt',
            'Agent Name',
            'Url',
            'Owner Name',
            'Email',
            'Mailing Address',
            'Square Feet',
        ]
        
        # Initialize Supabase connection
        if SUPABASE_AVAILABLE:
            self._init_supabase()
    
    def _init_supabase(self):
        """Initialize Supabase client"""
        try:
            # Load environment variables
            project_root = Path(__file__).resolve().parents[2] # Go up to Scraper_backend
            env_path = project_root / '.env'
            
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
            else:
                load_dotenv()
            
            SUPABASE_URL = os.getenv('SUPABASE_URL', '')
            SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '') or os.getenv('SUPABASE_ANON_KEY', '') or os.getenv('SUPABASE_KEY', '')
            
            if SUPABASE_URL and SUPABASE_KEY:
                self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                print("Supabase connection initialized successfully")
            else:
                print("Warning: Supabase credentials not found. Data will only be saved to CSV.")
        except Exception as e:
            print(f"Warning: Could not initialize Supabase: {e}. Data will only be saved to CSV.")
    
    def _extract_beds_baths(self, beds_baths_str):
        """Extract beds and baths from 'Beds / Baths' format"""
        beds = ""
        baths = ""
        
        if beds_baths_str:
            match = re.search(r'(\d+)\s*/\s*(\d+\.?\d*)', beds_baths_str)
            if match:
                beds = match.group(1)
                baths = match.group(2)
        
        return beds, baths
    
    def _clean_price(self, price_str):
        """Clean price string, remove $ and commas"""
        if not price_str:
            return ""
        cleaned = re.sub(r'[^\d]', '', price_str)
        return cleaned if cleaned else price_str
    
    def _upload_to_supabase(self, item_data, spider):
        """Upload item directly to Supabase"""
        if not self.supabase:
            return False
        
        try:
            # Extract beds and baths
            beds, baths = self._extract_beds_baths(item_data.get('Beds / Baths', ''))
            
            # Prepare record for Supabase
            record = {
                'address': item_data.get('Address', '').strip() or None,
                'price': self._clean_price(item_data.get('Asking Price', '')) or None,
                'beds': beds or None,
                'baths': baths or None,
                'square_feet': item_data.get('Square Feet', '').strip() or None,
                'listing_link': item_data.get('Url', '').strip() or None,
                'property_type': None,
                'county': None,
                'lot_acres': None,
                'owner_name': item_data.get('Owner Name', '').strip() or None,
                'mailing_address': item_data.get('Mailing Address', '').strip() or None,
                'scrape_date': datetime.now().strftime('%Y-%m-%d'),
                'emails': item_data.get('Email', '').strip() or None,
                'phones': item_data.get('Phone Number', '').strip() or None,
            }
            
            # Only upload if we have address or listing_link
            if not record['address'] and not record['listing_link']:
                return False
            
            # Upsert into Supabase to handle duplicates (on_conflict='listing_link')
            result = self.supabase.table('redfin_listings').upsert(
                record,
                on_conflict='listing_link'
            ).execute()
            
            if result.data:
                inserted_id = result.data[0].get('id', 'N/A')
                spider.logger.info(f"Uploaded to Supabase (ID: {inserted_id}): {record.get('address', 'N/A')}")
                return True
            else:
                spider.logger.warning(f"Failed to upload to Supabase: {record.get('address', 'N/A')}")
                return False
                
        except Exception as e:
            spider.logger.error(f"Error uploading to Supabase: {e}")
            return False

    def open_spider(self, spider):
        """Supabase is initialized in __init__"""
        pass

    def process_item(self, item, spider):
        """Process item: upload to Supabase directly"""
        adapter = ItemAdapter(item)
        
        # Map item fields to database columns
        field_mapping = {
            'Name': adapter.get('Name', ''),
            'Beds / Baths': adapter.get('Beds_Baths', ''),
            'Phone Number': adapter.get('Phone_Number', ''),
            'Asking Price': adapter.get('Asking_Price', ''),
            'Days On Redfin': adapter.get('Days_On_Redfin', ''),
            'Address': adapter.get('Address', ''),
            'YearBuilt': adapter.get('YearBuilt', ''),
            'Agent Name': adapter.get('Agent_Name', ''),
            'Url': adapter.get('Url', ''),
            'Owner Name': adapter.get('Owner_Name', ''),
            'Email': adapter.get('Email', ''),
            'Mailing Address': adapter.get('Mailing_Address', ''),
            'Square Feet': adapter.get('Square_Feet', ''),
        }
        
        # Upload to Supabase directly
        if self.supabase:
            self._upload_to_supabase(field_mapping, spider)
        
        return item

    def close_spider(self, spider):
        """Cleanup when spider closes"""
        pass
