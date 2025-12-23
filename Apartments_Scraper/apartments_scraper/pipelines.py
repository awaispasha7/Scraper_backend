# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import csv
import os
from itemadapter import ItemAdapter


class ApartmentsPipeline:
    def process_item(self, item, spider):
        return item


class ImmediateCsvPipeline:
    """
    Pipeline that writes items immediately to CSV file with flushing.
    This ensures items appear in CSV file right away, not buffered.
    """
    
    def __init__(self):
        self.csv_files = {}
        self.csv_writers = {}
        self.fieldnames = [
            "listing_url", "title", "price", "beds", "baths", "sqft",
            "owner_name", "owner_email", "phone_numbers", "full_address",
            "street", "city", "state", "zip_code", "neighborhood", "description"
        ]
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def open_spider(self, spider):
        """Open CSV file when spider starts."""
        try:
            # Get CSV filename from spider if available (should already be absolute path)
            if hasattr(spider, 'csv_filename'):
                csv_filename = spider.csv_filename
                # Ensure it's an absolute path
                if not os.path.isabs(csv_filename):
                    # If somehow not absolute, find project root
                    current_dir = os.getcwd()
                    project_root = current_dir
                    # Try to find scrapy.cfg by going up directories
                    check_dir = current_dir
                    for _ in range(5):  # Max 5 levels up
                        if os.path.exists(os.path.join(check_dir, 'scrapy.cfg')):
                            project_root = check_dir
                            break
                        parent = os.path.dirname(check_dir)
                        if parent == check_dir:  # Reached root
                            break
                        check_dir = parent
                    csv_filename = os.path.join(project_root, csv_filename)
            else:
                # Fallback: use default filename and find project root
                current_dir = os.getcwd()
                project_root = current_dir
                # Try to find scrapy.cfg by going up directories
                check_dir = current_dir
                for _ in range(5):  # Max 5 levels up
                    if os.path.exists(os.path.join(check_dir, 'scrapy.cfg')):
                        project_root = check_dir
                        break
                    parent = os.path.dirname(check_dir)
                    if parent == check_dir:  # Reached root
                        break
                    check_dir = parent
                csv_filename = os.path.join(project_root, 'output', 'apartments_frbo_chicago-il.csv')
            
            # Ensure output directory exists
            output_dir = os.path.dirname(csv_filename)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                spider.logger.info(f"📁 Output directory ensured: {output_dir}")
            
            # Check if file exists and has data rows (not just headers)
            file_exists = os.path.exists(csv_filename)
            has_data = False
            
            if file_exists:
                try:
                    with open(csv_filename, 'r', encoding='utf-8-sig') as f:
                        lines = f.readlines()
                        # If file has more than 1 line, it has data (line 1 = headers, line 2+ = data)
                        has_data = len(lines) > 1
                except Exception as e:
                    spider.logger.warning(f"Could not read existing CSV file: {e}")
                    has_data = False
            
            # If file exists but only has headers (or is empty), rewrite it
            if file_exists and not has_data:
                # File exists but only has headers - rewrite to start fresh
                csv_file = open(csv_filename, 'w', newline='', encoding='utf-8-sig')
                writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
                writer.writeheader()
                csv_file.flush()
                csv_file.close()
                spider.logger.info(f"📄 Rewrote CSV file with headers: {csv_filename}")
                # Now open in append mode for data
                csv_file = open(csv_filename, 'a', newline='', encoding='utf-8-sig')
                writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
            elif not file_exists:
                # New file - write headers first
                try:
                    csv_file = open(csv_filename, 'w', newline='', encoding='utf-8-sig')
                    writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
                    writer.writeheader()
                    csv_file.flush()
                    csv_file.close()
                    spider.logger.info(f"✅ Created new CSV file with headers: {csv_filename}")
                    # Verify file was created
                    if os.path.exists(csv_filename):
                        file_size = os.path.getsize(csv_filename)
                        spider.logger.info(f"✅ CSV file verified: {csv_filename} ({file_size} bytes)")
                    else:
                        spider.logger.error(f"❌ CSV file was not created: {csv_filename}")
                    # Now open in append mode for data
                    csv_file = open(csv_filename, 'a', newline='', encoding='utf-8-sig')
                    writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
                except Exception as e:
                    spider.logger.error(f"❌ Failed to create CSV file: {e}", exc_info=True)
                    raise  # Re-raise to stop spider if CSV can't be created
            else:
                # File exists and has data - just append
                csv_file = open(csv_filename, 'a', newline='', encoding='utf-8-sig')
                writer = csv.DictWriter(csv_file, fieldnames=self.fieldnames)
                spider.logger.info(f"📝 Appending to existing CSV file: {csv_filename}")
            
            self.csv_files[spider.name] = csv_file
            self.csv_writers[spider.name] = writer
            
            spider.logger.info(f"📝 Immediate CSV pipeline opened: {csv_filename}")
            spider.logger.info(f"📂 Full path: {os.path.abspath(csv_filename)}")
            
        except Exception as e:
            spider.logger.error(f"❌ CRITICAL: Failed to open CSV pipeline: {e}", exc_info=True)
            # Don't raise - let spider continue, but log the error
    
    def process_item(self, item, spider):
        """Write item to CSV immediately and flush."""
        try:
            if spider.name not in self.csv_writers:
                spider.logger.warning(f"⚠️ No CSV writer found for spider {spider.name}. Pipeline may not have opened correctly.")
                return item
            
            writer = self.csv_writers[spider.name]
            
            # Convert item to dict and ensure all fields are present
            item_dict = {}
            for field in self.fieldnames:
                item_dict[field] = item.get(field, '')
            
            # Write row immediately
            writer.writerow(item_dict)
            
            # Flush to disk immediately so data appears in file right away
            if spider.name in self.csv_files:
                self.csv_files[spider.name].flush()
            
            return item
        except Exception as e:
            spider.logger.error(f"❌ Error writing item to CSV: {e}", exc_info=True)
            return item  # Continue processing even if CSV write fails
    
    def close_spider(self, spider):
        """Close CSV file when spider closes."""
        if spider.name in self.csv_files:
            self.csv_files[spider.name].close()
            del self.csv_files[spider.name]
            del self.csv_writers[spider.name]
            spider.logger.info(f"📝 Immediate CSV pipeline closed for {spider.name}")


class SupabasePipeline:
    """
    Pipeline that automatically uploads items to Supabase as they're scraped.
    Uses upsert to handle duplicates (updates if listing_url exists, inserts if new).
    Only activates if Supabase credentials are available in environment variables or .env file.
    """
    
    def __init__(self):
        self.supabase_client = None
        self.enabled = False
        self.table_name = "apartments_frbo_chicago"
        self.upload_count = 0
        self.error_count = 0
        self.batch = []
        self.batch_size = 1  # Upload immediately (batch size 1)
    
    def load_env_file(self, spider=None):
        """Load environment variables from .env file if it exists."""
        # Check multiple possible locations for .env file
        current_file = os.path.abspath(__file__)
        # From pipelines.py: apartments_scraper -> Apartments_Scraper -> Scraper_backend
        script_dir = os.path.dirname(os.path.dirname(current_file))  # Apartments_Scraper
        possible_paths = [
            os.path.join(os.path.dirname(script_dir), '.env'),  # Scraper_backend root (1 level up)
            os.path.join(script_dir, '.env'),  # Apartments_Scraper/.env
            os.path.join(os.path.expanduser('~'), '.env'),  # Home directory
        ]
        
        env_path = None
        for path in possible_paths:
            if os.path.exists(path):
                env_path = path
                break
        
        if env_path:
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    loaded_count = 0
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key and value and key not in os.environ:
                                os.environ[key] = value
                                loaded_count += 1
                    if spider and loaded_count > 0:
                        spider.logger.debug(f"📄 Loaded {loaded_count} environment variable(s) from .env file: {env_path}")
            except Exception as e:
                if spider:
                    spider.logger.debug(f"⚠️  Error loading .env file: {e}")
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls()
    
    def open_spider(self, spider):
        """Connect to Supabase when spider starts."""
        try:
            # Load environment variables from .env file
            self.load_env_file(spider)
            
            # Check if Supabase credentials are available
            # Support multiple variable name formats (Next.js style and standard)
            supabase_url = (
                os.getenv("SUPABASE_URL") or 
                os.getenv("NEXT_PUBLIC_SUPABASE_URL")
            )
            
            supabase_key = (
                os.getenv("SUPABASE_KEY") or 
                os.getenv("SUPABASE_SERVICE_ROLE_KEY") or 
                os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
            )
            
            # Debug logging
            if spider:
                spider.logger.debug(f"🔍 Checking Supabase credentials...")
                spider.logger.debug(f"   SUPABASE_URL: {'Found' if os.getenv('SUPABASE_URL') else 'Not found'}")
                spider.logger.debug(f"   NEXT_PUBLIC_SUPABASE_URL: {'Found' if os.getenv('NEXT_PUBLIC_SUPABASE_URL') else 'Not found'}")
                spider.logger.debug(f"   SUPABASE_KEY: {'Found' if os.getenv('SUPABASE_KEY') else 'Not found'}")
                spider.logger.debug(f"   SUPABASE_SERVICE_ROLE_KEY: {'Found' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'Not found'}")
                spider.logger.debug(f"   NEXT_PUBLIC_SUPABASE_ANON_KEY: {'Found' if os.getenv('NEXT_PUBLIC_SUPABASE_ANON_KEY') else 'Not found'}")
                spider.logger.debug(f"   Final supabase_url: {'Found' if supabase_url else 'Not found'}")
                spider.logger.debug(f"   Final supabase_key: {'Found' if supabase_key else 'Not found'}")
            
            if not supabase_url or not supabase_key:
                spider.logger.info(
                    "ℹ️  Supabase credentials not found. Supabase pipeline disabled.\n"
                    "   To enable: Set SUPABASE_URL and SUPABASE_KEY in .env file or environment variables.\n"
                    "   (Also supports NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY)"
                )
                self.enabled = False
                return
            
            # Try to import supabase
            try:
                from supabase import create_client
            except ImportError:
                spider.logger.warning(
                    "⚠️  supabase package not installed. Supabase pipeline disabled.\n"
                    "   To enable: pip install supabase"
                )
                self.enabled = False
                return
            
            # Create Supabase client
            try:
                self.supabase_client = create_client(supabase_url, supabase_key)
                self.enabled = True
                spider.logger.info(f"✅ Supabase pipeline enabled - connected to {supabase_url}")
                spider.logger.info(f"📊 Table: {self.table_name}")
            except Exception as e:
                spider.logger.warning(f"⚠️  Failed to connect to Supabase: {e}. Supabase pipeline disabled.")
                self.enabled = False
                
        except Exception as e:
            spider.logger.warning(f"⚠️  Error initializing Supabase pipeline: {e}. Pipeline disabled.")
            self.enabled = False
    
    def process_item(self, item, spider):
        """Upload item to Supabase."""
        if not self.enabled or not self.supabase_client:
            return item
        
        try:
            # Convert item to dict
            item_dict = {}
            fieldnames = [
                "listing_url", "title", "price", "beds", "baths", "sqft",
                "owner_name", "owner_email", "phone_numbers", "full_address",
                "street", "city", "state", "zip_code", "neighborhood", "description"
            ]
            
            for field in fieldnames:
                value = item.get(field, '')
                # Convert empty strings to None for better database handling
                item_dict[field] = value.strip() if value and str(value).strip() else None
            
            # Add to batch
            self.batch.append(item_dict)
            
            # Upload batch when it reaches batch_size
            if len(self.batch) >= self.batch_size:
                self._upload_batch(spider)
            
            return item
            
        except Exception as e:
            self.error_count += 1
            spider.logger.error(f"❌ Error preparing item for Supabase: {e}", exc_info=True)
            return item  # Continue processing even if Supabase upload fails
    
    def _upload_batch(self, spider):
        """Upload a batch of items to Supabase."""
        if not self.batch:
            return
        
        try:
            # Use upsert to handle duplicates (update if listing_url exists, insert if new)
            result = self.supabase_client.table(self.table_name).upsert(
                self.batch,
                on_conflict="listing_url"
            ).execute()
            
            batch_count = len(self.batch)
            self.upload_count += batch_count
            self.batch = []  # Clear batch after successful upload
            
            spider.logger.debug(f"📤 Uploaded {batch_count} items to Supabase (total: {self.upload_count})")
            
        except Exception as e:
            self.error_count += len(self.batch)
            spider.logger.error(f"❌ Error uploading batch to Supabase: {e}")
            # Try uploading items one by one to see which ones fail
            failed_items = []
            for item in self.batch:
                try:
                    self.supabase_client.table(self.table_name).upsert(
                        item,
                        on_conflict="listing_url"
                    ).execute()
                    self.upload_count += 1
                except Exception as single_error:
                    failed_items.append(item.get('listing_url', 'Unknown'))
                    spider.logger.debug(f"   ⚠️  Failed to upload: {item.get('listing_url', 'Unknown')[:50]}... - {single_error}")
            
            self.batch = []  # Clear batch even if some failed
    
    def close_spider(self, spider):
        """Upload remaining items and close Supabase connection when spider closes."""
        if not self.enabled:
            return
        
        # Upload any remaining items in the batch
        if self.batch:
            self._upload_batch(spider)
        
        # Log summary
        if self.upload_count > 0:
            spider.logger.info(
                f"📊 Supabase upload summary:\n"
                f"   ✅ Successfully uploaded: {self.upload_count} listings\n"
                f"   {'⚠️  Errors: ' + str(self.error_count) if self.error_count > 0 else ''}"
            )
        else:
            spider.logger.info("ℹ️  No items uploaded to Supabase (pipeline was disabled or no items processed)")
