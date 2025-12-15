"""
Scrapy spider to scrape all For Rent By Owner listings from Chicago, IL.
Uses Zyte API via middleware to bypass bot detection.
Target: https://www.apartments.com/chicago-il/for-rent-by-owner/
Expected: 1,300+ listings (number may change)
"""

import os
import re
import json
import sys
import scrapy
from apartments_scraper.items import FrboListingItem

# Add project root to path for progress_tracker import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from progress_tracker import ProgressTracker
except ImportError:
    ProgressTracker = None


class ApartmentsFrboSpider(scrapy.Spider):
    name = "apartments_frbo"
    allowed_domains = ["apartments.com"]
    
    # Custom settings for this spider - tuned for Apartments.com FRBO (balance speed + bans)
    # Note: FEEDS filename is set dynamically in __init__ based on city parameter
    # Apartments.com has stronger anti-bot protection than Zillow, so we need more conservative settings
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        # Slightly more aggressive concurrency to speed up crawl
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
        # Lower delay (Zyte handles most blocking; this improves total runtime)
        "DOWNLOAD_DELAY": 0.15,
        "RANDOMIZE_DOWNLOAD_DELAY": True,  # Re-enabled to appear more human-like
        "DOWNLOAD_DELAY_RANDOMIZE": 0.3,  # Randomize delay by 30% (0.35s to 0.65s range)
        # AutoThrottle still enabled, but capped so it doesn't slow to a crawl
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 3.0,
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
        "RETRY_HTTP_CODES": [412, 404, 429, 500, 502, 503, 504, 522, 524],  # Removed 520 - handled by error handler
        # Enable immediate CSV pipeline for real-time data saving
        # Enable Supabase pipeline for automatic database updates (runs after CSV)
        "ITEM_PIPELINES": {
            "apartments_scraper.pipelines.ImmediateCsvPipeline": 300,
            "apartments_scraper.pipelines.SupabasePipeline": 400,  # Runs after CSV pipeline
        },
    }
    
    def __init__(self, city="chicago-il", url=None, resume=False, *args, **kwargs):
        """Initialize spider with optional city parameter or custom URL.
        
        Args:
            city: City name in format like "chicago-il" (used if url is not provided)
            url: Custom URL to scrape (overrides city parameter if provided)
            resume: If True, resume from saved progress (default: False)
        """
        super(ApartmentsFrboSpider, self).__init__(*args, **kwargs)
        
        # Store resume flag
        self.resume = str(resume).lower() in ('true', '1', 'yes')
        
        # Store custom URL if provided
        self.start_url = url
        
        # If URL is provided, extract city from URL or use default
        if url:
            # Try to extract city from URL
            city_match = re.search(r'/([a-z]+(?:-[a-z]+)+)/for-rent-by-owner', url.lower())
            if city_match:
                self.city = city_match.group(1)
                self.logger.info(f"📍 Extracted city '{self.city}' from provided URL")
            else:
                # Use provided city or default
                self.city = city
                self.logger.info(f"📍 Using city '{self.city}' (could not extract from URL)")
        else:
            # Validate city format (should be like "chicago-il" or "new-york-ny")
            if not city or not isinstance(city, str):
                raise ValueError("City parameter must be a non-empty string (e.g., 'chicago-il')")
            if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)+$', city.lower()):
                self.logger.warning(f"City parameter '{city}' may not be in expected format (e.g., 'chicago-il'). Proceeding anyway...")
            
            self.city = city
        
        # Find project root (where scrapy.cfg is located)
        # This ensures the output folder is always in the correct location
        current_file = os.path.abspath(__file__)
        # Navigate up from: apartments_scraper/spiders/apartments_frbo.py
        # To: apartments/ (project root where scrapy.cfg is)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        # Ensure output directory exists in project root
        output_dir = os.path.join(project_root, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Set CSV filename for immediate pipeline writing (use absolute path)
        # The ImmediateCsvPipeline will write items immediately (not buffered like FEEDS)
        csv_filename = os.path.join(output_dir, f"apartments_frbo_{self.city}.csv")
        
        # Store filename for pipeline and logging
        self.csv_filename = csv_filename
        
        # Initialize progress tracker
        self.progress_tracker = None
        if ProgressTracker:
            self.progress_tracker = ProgressTracker(self.city, output_dir)
        
        # IMPROVEMENT: Duplicate prevention - track scraped URLs (like Zillow scraper)
        self.seen_urls = set()
        self.duplicate_count = 0
        
        # Track failed pages to automatically skip blocked pages
        self._failed_pages = {}  # {page_num: failure_count}
        # Track consecutive blocked pages to prevent infinite loops
        self._consecutive_blocked_pages = 0
        
        # Resume from saved progress if requested
        self._resume_page = None
        # Initialize total_listings_found to 0 - will be set from CSV count if resuming
        self._total_listings_found = 0
        
        if self.resume and self.progress_tracker:
            progress_data, csv_count, csv_urls = self.progress_tracker.get_resume_info()
            
            if progress_data:
                resume_page = self.progress_tracker.get_resume_page()
                
                # If resume_page is 0 or None, but we have listings in CSV, start from page 1
                # This handles cases where progress file was reset but CSV has data
                if (resume_page is None or resume_page == 0) and csv_count > 0:
                    # Start from page 1 and skip duplicates - this is safer and avoids blocked pages
                    self._resume_page = 1
                    self.logger.info(f"🔄 Progress file shows page 0, but CSV has {csv_count} listings. Starting from page 1 and skipping duplicates.")
                elif resume_page and resume_page > 50:
                    # If resume page is very high (>50), start from page 1 to avoid blocked pages
                    # High page numbers are often blocked by the website
                    self._resume_page = 1
                    self.logger.warning(
                        f"🔄 Resume page {resume_page} is very high (likely blocked). Starting from page 1 instead "
                        f"to avoid blocked pages. Will skip {csv_count} duplicates from CSV."
                    )
                else:
                    # Start from a few pages before the resume page to catch any missed listings
                    # This helps if some pages were skipped due to errors
                    if resume_page and resume_page > 3:
                        self._resume_page = max(1, resume_page - 2)  # Start 2 pages earlier
                        self.logger.info(f"🔄 Starting from page {self._resume_page} (2 pages before saved page {resume_page}) to catch any missed listings")
                    else:
                        self._resume_page = resume_page if resume_page else 1
                
                # Load URLs from CSV to skip duplicates
                self.seen_urls.update(csv_urls)
                # FIX: Initialize total_listings_found with CSV count (actual listings found)
                # This is the real count, not the outdated progress file value
                self._total_listings_found = csv_count
                # Reset consecutive_empty_pages when resuming - start fresh
                # The old value might cause premature stopping
                self._consecutive_empty_pages = 0
                self.logger.info(f"🔄 RESUME MODE: Found {csv_count} listings in CSV, {len(csv_urls)} unique URLs")
                self.logger.info(f"🔄 Will resume from page {self._resume_page}")
                self.logger.info(f"🔄 Will skip {len(csv_urls)} URLs already in CSV")
                self.logger.info(f"📊 Initialized total_listings_found to {csv_count} (from CSV count, not progress file)")
            elif csv_count > 0:
                # CSV exists but no progress file - load URLs to skip duplicates
                # Start from page 1 to avoid blocked pages
                self._resume_page = 1
                self.seen_urls.update(csv_urls)
                # Initialize with CSV count
                self._total_listings_found = csv_count
                self.logger.info(f"📄 Found {csv_count} listings in CSV, will skip duplicates")
                self.logger.info(f"📄 Starting from page 1 and will skip {len(csv_urls)} URLs already in CSV")
                self.logger.info(f"📊 Initialized total_listings_found to {csv_count} (from CSV count)")
        
        # Remove FEEDS to avoid conflicts - using ImmediateCsvPipeline instead
        # FEEDS buffers items and may not show data immediately
        if "FEEDS" in self.custom_settings:
            del self.custom_settings["FEEDS"]
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """Create spider instance and connect cleanup signal."""
        spider = super(ApartmentsFrboSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=scrapy.signals.spider_closed)
        crawler.signals.connect(spider.spider_opened, signal=scrapy.signals.spider_opened)
        return spider
    
    def spider_opened(self, spider):
        """Called when spider is opened - create CSV file with headers immediately."""
        # NOTE: The pipeline's open_spider() method should create the CSV file
        # This is a backup to ensure it's created even if pipeline fails
        csv_path = self.csv_filename
        if csv_path:
            try:
                import csv
                # Ensure output directory exists
                output_dir = os.path.dirname(csv_path)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                
                # Create file with headers if it doesn't exist or is empty
                if not os.path.exists(csv_path) or (os.path.exists(csv_path) and os.path.getsize(csv_path) == 0):
                    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            "listing_url", "title", "price", "beds", "baths", "sqft",
                            "owner_name", "owner_email", "phone_numbers", "full_address",
                            "street", "city", "state", "zip_code", "neighborhood", "description"
                        ])
                    self.logger.info(f"📄 CSV file created with headers (backup method): {csv_path}")
                    # Verify it was created
                    if os.path.exists(csv_path):
                        self.logger.info(f"✅ CSV file verified at: {os.path.abspath(csv_path)}")
                    else:
                        self.logger.error(f"❌ CSV file was NOT created at: {csv_path}")
            except Exception as e:
                self.logger.error(f"❌ CRITICAL: Could not create CSV file: {e}", exc_info=True)
    
    def start_requests(self):
        """Start from the main FRBO search page."""
        # IMPORTANT: CSV file should already be created by pipeline's open_spider method
        # But we log the path here for visibility
        self.logger.info(f"📄 CSV file should be at: {self.csv_filename}")
        self.logger.info(f"📂 Full CSV path: {os.path.abspath(self.csv_filename)}")
        
        # Validate Zyte API key before starting
        api_key = self.crawler.settings.get("ZYTE_API_KEY")
        if not api_key:
            # os is already imported at the top of the file, no need to import again
            api_key = os.getenv("ZYTE_API_KEY")
            if not api_key:
                # Try reading from .env file
                package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                env_path = os.path.join(package_dir, ".env")
                if os.path.exists(env_path):
                    try:
                        with open(env_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("ZYTE_API_KEY="):
                                    api_key = line.split("=", 1)[1].strip()
                                    break
                    except Exception as e:
                        self.logger.warning(f"Could not read .env file: {e}")
        
        if not api_key:
            self.logger.error("❌ ZYTE_API_KEY not found! Please set it in:")
            self.logger.error("   1. Environment variable: $env:ZYTE_API_KEY='your_key'")
            self.logger.error("   2. Settings file: ZYTE_API_KEY='your_key'")
            self.logger.error("   3. apartments_scraper/.env file: ZYTE_API_KEY=your_key")
            self.logger.error("⚠️ Spider will not start without API key, but CSV file should still be created.")
            # Even if API key is missing, the pipeline should have created the CSV file
            # Check if file exists
            if os.path.exists(self.csv_filename):
                self.logger.info(f"✅ CSV file exists: {self.csv_filename}")
            else:
                self.logger.warning(f"⚠️ CSV file not found: {self.csv_filename}")
            return
        
        self.logger.info("✅ Zyte API key found, starting crawl...")
        
        # Use custom URL if provided, otherwise construct from city
        if self.start_url:
            url = self.start_url.strip()
            # Clean URL - remove any invalid characters or trailing text
            # Fix common issues like "partments>" or other appended text
            if url.endswith('>') or url.endswith('partments>'):
                # Remove trailing invalid characters
                url = re.sub(r'[^/]+>$', '', url)
                # Ensure it ends with / if it's a directory URL
                if '/for-rent-by-owner' in url and not url.endswith('/'):
                    url = url.rstrip('>').rstrip('partments') + '/'
            # Ensure URL is properly formatted
            if '/for-rent-by-owner' in url:
                # Remove any text after the path
                match = re.search(r'(https://www\.apartments\.com/[^/]+/for-rent-by-owner/?[^>]*)', url)
                if match:
                    url = match.group(1).rstrip('>').rstrip('partments')
                    if not url.endswith('/'):
                        url += '/'
            self.logger.info(f"🌐 Using provided URL (cleaned): {url}")
        else:
            url = f"https://www.apartments.com/{self.city}/for-rent-by-owner/"
            self.logger.info(f"🏙️ Constructed URL from city '{self.city}': {url}")
        
        # Validate URL
        if not url.startswith("http"):
            self.logger.error(f"❌ Invalid URL format: {url}")
            return
        
        # Final validation - ensure URL matches expected pattern
        if not re.match(r'https://www\.apartments\.com/[^/]+/for-rent-by-owner/?', url):
            self.logger.warning(f"⚠️ URL doesn't match expected pattern, but proceeding: {url}")
        
        # Store base URL for pagination (normalize to remove trailing slash)
        self._base_url = url.rstrip('/')
        
        # If resuming, start from the resume page
        # Allow resuming from page 1 or higher (changed from > 1 to >= 1)
        if self._resume_page is not None and self._resume_page >= 1:
            # Use path-based format: /{page}/ instead of ?page={page}
            resume_url = f"{url.rstrip('/')}/{self._resume_page}/"
            self.logger.info(f"🔄 RESUMING: Starting from page {self._resume_page}")
            self.logger.info(f"🔄 Resume URL: {resume_url}")
            yield scrapy.Request(resume_url, callback=self.parse_search, errback=self.handle_error, dont_filter=True)
        else:
            self.logger.info(f"🚀 Starting crawl from: {url}")
            self.logger.info(f"📄 CSV file will be created at: {self.csv_filename}")
            self.logger.info("💾 Data will be saved incrementally as items are scraped...")
            yield scrapy.Request(url, callback=self.parse_search)
    
    def parse_search(self, response):
        """
        Parse the search results page:
        - Extract listing data from search page cards (IMPROVEMENT: like Zillow)
        - Extract listing URLs and follow to detail pages for additional info
        - Follow pagination (Next page)
        """
        # Track page number for progress logging
        if not hasattr(self, '_page_count'):
            # Initialize counters
            self._page_count = 0
            # _total_listings_found is already set in __init__ from CSV count if resuming
            if not hasattr(self, '_total_listings_found'):
                self._total_listings_found = 0
            self._items_from_search_page = 0
            self._total_listings_on_site = None
            self._consecutive_empty_pages = 0  # Track consecutive pages with 0 listings
            self._consecutive_blocked_pages = 0  # Track consecutive blocked pages
            
            # If resuming, load saved progress
            if self.resume and self.progress_tracker:
                progress_data = self.progress_tracker.load_progress()
                if progress_data:
                    # FIX: Use _resume_page if available (set in __init__), otherwise use progress file
                    # _resume_page is more accurate as it accounts for CSV count estimation
                    if hasattr(self, '_resume_page') and self._resume_page and self._resume_page > 0:
                        resume_page = self._resume_page
                        self._page_count = max(0, resume_page - 1)  # Will be incremented to resume_page
                    else:
                        # Fallback to progress file value
                        resume_page = progress_data.get('page_count', 0)
                        self._page_count = max(0, resume_page - 1)  # Will be incremented to resume_page
                    
                    # Don't overwrite _total_listings_found - it's already set from CSV count in __init__
                    # The CSV count is the real count, progress file value might be outdated
                    if self._total_listings_found == 0:
                        # Only use progress file value if CSV count wasn't available
                        self._total_listings_found = progress_data.get('total_listings_found', 0)
                    # Reset consecutive_empty_pages to 0 when resuming - start fresh
                    # The old value (6) would cause immediate stopping
                    # We want to start fresh and only stop after 6 NEW empty pages
                    self._consecutive_empty_pages = 0
                    self.logger.info(f"🔄 Loaded saved progress: resuming from page {resume_page}, {self._total_listings_found} listings found (from CSV count)")
        
        self._page_count += 1
        
        # Reset consecutive blocked pages counter on successful page load
        if hasattr(self, '_consecutive_blocked_pages'):
            self._consecutive_blocked_pages = 0
            self.logger.debug(f"✅ Page {self._page_count} loaded successfully - reset consecutive blocked pages counter")
        
        # Extract total listings count from page (e.g., "1,575 Rentals")
        if not self._total_listings_on_site:
            # Try multiple XPath patterns to find total listings count
            # The website shows "1,013 Rentals" - need comprehensive detection
            total_listings_text = (
                response.xpath("//h1[contains(text(),'Rentals')]//text()").get()
                or response.xpath("//h1[contains(text(),'Rental')]//text()").get()
                or response.xpath("//div[contains(@class,'resultsHeader')]//text()[contains(.,'Rentals')]").get()
                or response.xpath("//div[contains(@class,'resultsHeader')]//text()[contains(.,'Rental')]").get()
                or response.xpath("//span[contains(text(),'Rentals')]//text()").get()
                or response.xpath("//span[contains(text(),'Rental')]//text()").get()
                or response.xpath("//*[contains(text(),'For Rent by Private Owner')]//following-sibling::*[contains(text(),'Rentals')]//text()").get()
                or response.xpath("//*[contains(text(),'For Rent by Private Owner')]/following::*[contains(text(),'Rentals')]//text()").get()
                or response.xpath("//*[contains(@class,'results')]//*[contains(text(),'Rentals')]//text()").get()
            )
            
            # If no direct match, try searching all text nodes for pattern
            if not total_listings_text:
                all_text = response.xpath("//text()").getall()
                rental_texts = [t.strip() for t in all_text if t and 'rental' in t.lower() and any(c.isdigit() for c in t)]
                if rental_texts:
                    # Get the first text that looks like a count (contains comma or large number)
                    for text in rental_texts[:10]:
                        if re.search(r'[\d,]+', text):
                            total_listings_text = text
                            self.logger.debug(f"🔍 Found potential rental count text: {text}")
                            break
            
            if total_listings_text:
                # Extract number from text (e.g., "1,013 Rentals", "945 Rentals", "1,575 Rentals" -> 1013, 945, 1575)
                # Try multiple patterns to catch different formats
                match = (
                    re.search(r'([\d,]+)\s+Rentals?', total_listings_text, re.IGNORECASE)
                    or re.search(r'([\d,]+)\s*Rentals?', total_listings_text, re.IGNORECASE)
                    or re.search(r'([\d,]+)', total_listings_text)
                )
                if match:
                    total_str = match.group(1).replace(',', '')
                    try:
                        self._total_listings_on_site = int(total_str)
                        self.logger.info(f"📊 Found total listings on site: {self._total_listings_on_site:,}")
                        # Estimate total pages (assuming ~20-25 listings per page - more conservative)
                        avg_listings_per_page = 25
                        estimated_pages = (self._total_listings_on_site + avg_listings_per_page - 1) // avg_listings_per_page
                        # Only set if we don't already have a more accurate count
                        if not hasattr(self, '_total_pages') or self._total_pages is None:
                            self._total_pages = estimated_pages
                            self.logger.info(f"📊 Estimated total pages: {self._total_pages} (based on {self._total_listings_on_site:,} listings at ~{avg_listings_per_page} per page)")
                    except ValueError:
                        self.logger.warning(f"⚠️ Could not parse total listings from text: {total_listings_text}")
                else:
                    self.logger.debug(f"🔍 Could not extract number from text: {total_listings_text}")
            else:
                # Log that we couldn't find the count - this helps debug
                self.logger.warning("⚠️ Could not find total listings count on page. Will use default target of 1000.")
                # If we're resuming and have CSV data, try to estimate target from website
                # The website shows 807 listings, so we should target at least that
                if self.resume and self._total_listings_found > 0:
                    # Set a minimum target of 807 (as shown on website) or more if we already have more
                    estimated_target = max(807, self._total_listings_found + 50)
                    self._total_listings_on_site = estimated_target
                    self.logger.info(f"📊 Using estimated target of {estimated_target} listings (website shows 807, continuing until we get all)")
        
        # DEBUG: Save first search page HTML to inspect structure (optional, can be disabled)
        if not hasattr(self, '_first_search_page_saved'):
            debug_enabled = self.crawler.settings.getbool("DEBUG_SAVE_HTML", False)
            if debug_enabled:
                with open('output/debug_search_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info("Saved first search page HTML to output/debug_search_page.html")
            self._first_search_page_saved = True
        
        # IMPROVEMENT: Try to extract JSON-LD data first (bulk extraction from search page)
        self.logger.info(f"🔍 Page {self._page_count}: Attempting JSON-LD bulk extraction...")
        json_listings = self._extract_from_json(response)
        json_ld_success = False
        if json_listings:
            json_ld_success = True
            self.logger.info(f"✅ Page {self._page_count}: JSON-LD extraction SUCCESS - Found {len(json_listings)} listings")
            self._items_from_search_page += len(json_listings)
            self.logger.info(f"📊 Processing {len(json_listings)} listings from JSON-LD...")
            
            processed_count = 0
            skipped_count = 0
            for listing_idx, listing_data in enumerate(json_listings, 1):
                url = listing_data.get('url', '')
                if not url or url in self.seen_urls:
                    skipped_count += 1
                    if not url:
                        self.logger.debug(f"⚠️ Listing #{listing_idx}: Skipped (no URL)")
                    else:
                        self.logger.debug(f"⚠️ Listing #{listing_idx}: Skipped (duplicate: {url[:50]}...)")
                    continue
                
                # Normalize URL
                if url.startswith("/"):
                    url = "https://www.apartments.com" + url
                elif not url.startswith("http"):
                    skipped_count += 1
                    self.logger.debug(f"⚠️ Listing #{listing_idx}: Skipped (invalid URL format: {url[:50]}...)")
                    continue
                
                self.seen_urls.add(url)
                
                # Create partial item with data from JSON-LD
                item = FrboListingItem()
                item["listing_url"] = url
                item["title"] = self.sanitize_text(listing_data.get('title', ''))
                item["price"] = self.sanitize_text(listing_data.get('price', ''))
                item["description"] = self.sanitize_text(listing_data.get('description', ''))
                
                # Extract phone number if available
                phone = listing_data.get('telephone', '')
                if phone:
                    item["phone_numbers"] = self.sanitize_text(phone)
                
                # Extract address components
                address = listing_data.get('address', {})
                if address:
                    item["street"] = self.sanitize_text(address.get('street', ''))
                    item["city"] = self.sanitize_text(address.get('city', ''))
                    item["state"] = self.sanitize_text(address.get('state', ''))
                    item["zip_code"] = self.sanitize_text(address.get('zip', ''))
                    
                    # Build full address
                    address_parts = [
                        address.get('street', ''),
                        address.get('city', ''),
                        address.get('state', ''),
                        address.get('zip', '')
                    ]
                    full_address = ', '.join([p for p in address_parts if p])
                    item["full_address"] = self.sanitize_text(full_address)
                
                # Note: beds, baths, sqft, email, owner_name still need to be extracted from detail page
                # But we have URL, title, price, phone, address from JSON-LD - this is huge!
                processed_count += 1
                if listing_idx <= 5 or listing_idx % 10 == 0:
                    self.logger.debug(f"📋 [{listing_idx}/{len(json_listings)}] {item.get('title', 'N/A')[:40]}... | {item.get('price', 'N/A')} | {item.get('phone_numbers', 'N/A')}")
                
                # Visit detail page for remaining fields (beds, baths, sqft, email, owner_name)
                yield response.follow(url, callback=self.parse_detail, 
                                     meta={'partial_item': item}, errback=self.handle_error)
            
            self.logger.info(f"✅ Page {self._page_count}: Processed {processed_count} listings from JSON-LD (skipped: {skipped_count})")
            self.logger.info(f"🚀 JSON-LD bulk extraction complete - skipping slower HTML extraction")
            # Track listings found on this page
            listings_on_page = processed_count
            self._total_listings_found += listings_on_page
            
            # FIX: Only count as "empty" if page truly has NO listings at all
            # Pages with duplicates are NOT empty - they have listings, just already scraped
            total_listings_on_page = processed_count + skipped_count  # Total found (new + duplicates)
            if total_listings_on_page == 0:
                # Truly empty page - no listings found at all
                self._consecutive_empty_pages += 1
                self.logger.warning(f"⚠️ Page {self._page_count}: Truly empty - no listings found at all (Consecutive empty pages: {self._consecutive_empty_pages})")
            elif processed_count > 0:
                # Found new listings - reset counter
                self._consecutive_empty_pages = 0
            else:
                # Page has listings but all are duplicates - don't count as empty
                # This means we're in a region we've already scraped, but there might be more pages ahead
                self.logger.info(f"ℹ️ Page {self._page_count}: Found {total_listings_on_page} listings (all duplicates) - not counting as empty page")
                # Don't increment consecutive_empty_pages - keep it at current value
                # We want to continue past duplicate regions to find new listings
            
            # Log progress toward target (use website total if detected, otherwise 1000)
            # Ensure we target at least 807 (website shows 807 listings)
            min_target = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
            if self._total_listings_found < min_target:
                remaining = min_target - self._total_listings_found
                self.logger.info(f"🎯 Progress: {self._total_listings_found}/{min_target} listings ({remaining} remaining to reach target)")
            else:
                self.logger.info(f"🎯 Target reached! {self._total_listings_found} listings scraped (target: {min_target}+)")
            
            # Save progress after processing page
            if self.progress_tracker:
                items_scraped = getattr(self, '_items_scraped', 0)
                self.progress_tracker.save_progress(
                    page_count=self._page_count,
                    total_listings_found=self._total_listings_found,
                    last_url=response.url,
                    items_scraped=items_scraped,
                    consecutive_empty_pages=self._consecutive_empty_pages
                )
            
            # JSON-LD extraction successful - skip HTML extraction and go to pagination
        
        # Fallback: Extract listing cards from HTML if JSON-LD extraction failed
        # (This is the original method - slower but more reliable)
        if not json_ld_success:
            self.logger.warning(f"⚠️ Page {self._page_count}: JSON-LD extraction failed - falling back to HTML extraction")
            placards = response.xpath("//article[contains(@class,'placard')]")
            listing_urls = set()
            items_from_cards = []
            
            for placard in placards:
                try:
                    # Extract URL
                    url = placard.xpath("./@data-url").get()
                    if not url:
                        url = placard.xpath(".//a[contains(@class,'property-link')]/@href").get()
                    
                    if not url:
                        continue
                    
                    url = url.strip()
                    # Normalize URLs
                    if url.startswith("/"):
                        url = "https://www.apartments.com" + url
                    elif not url.startswith("http"):
                        continue
                    
                    # Filter to actual listing URLs
                    # NOTE: Previously this required the URL to contain f"-{self.city}/",
                    # which *excluded* many nearby-area FRBO listings that still appear
                    # in the search results count (e.g. suburbs around Chicago).
                    # We now only do a light sanity check so we keep all results the
                    # Apartments.com search page shows (so you can reach ~1200+ units).
                    if url.count("/") < 4:
                        continue
                    
                    # IMPROVEMENT: Skip duplicates
                    if url in self.seen_urls:
                        self.duplicate_count += 1
                        continue
                    
                    self.seen_urls.add(url)
                    listing_urls.add(url)
                    
                    # IMPROVEMENT: Extract basic data from search page card (like Zillow)
                    item = FrboListingItem()
                    item["listing_url"] = url
                    
                    # Extract title
                    title = placard.xpath(".//a[contains(@class,'property-link')]//text()").get()
                    if not title:
                        title = placard.xpath(".//span[contains(@class,'propertyTitle')]//text()").get()
                    item["title"] = self.sanitize_text(title) if title else ""
                    
                    # Extract price from search page
                    price = placard.xpath(".//span[contains(@class,'rentDisplay')]//text()").get()
                    if not price:
                        price = placard.xpath(".//p[contains(@class,'property-pricing')]//text()").get()
                    if price:
                        price_match = re.search(r'\$[\d,]+', price)
                        if price_match:
                            item["price"] = price_match.group(0)
                    
                    # Extract beds/baths from search page
                    beds_baths = placard.xpath(".//span[contains(@class,'bedRange') or contains(@class,'bathRange')]//text()").getall()
                    if beds_baths:
                        beds_baths_text = " ".join(beds_baths)
                        beds_match = re.search(r'(\d+)\s*Bed', beds_baths_text, re.I)
                        if beds_match:
                            item["beds"] = beds_match.group(1)
                        baths_match = re.search(r'(\d+(?:\.\d+)?)\s*Bath', beds_baths_text, re.I)
                        if baths_match:
                            item["baths"] = str(int(float(baths_match.group(1))))
                    
                    # Store partial item for detail page enhancement
                    items_from_cards.append((url, item))
                    
                except Exception as e:
                    self.logger.warning(f"Error extracting from placard: {e}")
                    continue
            
            listings_on_page = len(listing_urls)
            self._total_listings_found += listings_on_page
            self.logger.info(f"📄 Page {self._page_count}: Found {listings_on_page} listing URLs (Total so far: {self._total_listings_found}, Duplicates skipped: {self.duplicate_count})")
            
            # Track consecutive empty pages
            if listings_on_page == 0:
                self._consecutive_empty_pages += 1
                self.logger.warning(f"⚠️ Page {self._page_count}: No listing URLs found! (Consecutive empty pages: {self._consecutive_empty_pages})")
                # Try to find ANY links as fallback
                all_links = response.xpath("//a/@href").getall()
                self.logger.debug(f"Total links on page: {len(all_links)}")
                sample_links = [l for l in all_links[:10] if l and ('chicago' in l.lower() or 'apartments.com' in l.lower())]
                self.logger.debug(f"Sample links: {sample_links[:5]}")
            else:
                # Reset consecutive empty pages counter if we found listings
                self._consecutive_empty_pages = 0
            
            # Log progress toward target (use website total if detected, otherwise 1000)
            # Ensure we target at least 807 (website shows 807 listings)
            min_target = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
            if self._total_listings_found < min_target:
                remaining = min_target - self._total_listings_found
                self.logger.info(f"🎯 Progress: {self._total_listings_found}/{min_target} listings ({remaining} remaining to reach target)")
            else:
                self.logger.info(f"🎯 Target reached! {self._total_listings_found} listings scraped (target: {min_target}+)")
            
            # Save progress after processing page
            if self.progress_tracker:
                items_scraped = getattr(self, '_items_scraped', 0)
                self.progress_tracker.save_progress(
                    page_count=self._page_count,
                    total_listings_found=self._total_listings_found,
                    last_url=response.url,
                    items_scraped=items_scraped,
                    consecutive_empty_pages=self._consecutive_empty_pages
                )
            
            # Follow each listing to detail page (with partial item data)
            for url, partial_item in items_from_cards:
                yield response.follow(url, callback=self.parse_detail, 
                                    meta={'partial_item': partial_item}, errback=self.handle_error)
        
        # Pagination: find next page link (improved selectors with fallback methods)
        next_page = None
        
        # METHOD 1: Try to extract total page count from pagination HTML
        if not hasattr(self, '_total_pages'):
            self._total_pages = None
            # Try to find total pages from pagination text (e.g., "Page 1 of 63")
            total_pages_text = (
                response.xpath("//span[contains(text(),'Page') and contains(text(),'of')]/text()").get()
                or response.xpath("//div[contains(@class,'paging')]//text()[contains(.,'of')]").get()
                or response.xpath("//nav[contains(@class,'pagination')]//text()[contains(.,'of')]").get()
            )
            if total_pages_text:
                # Extract number after "of" (e.g., "Page 1 of 63" -> 63)
                match = re.search(r'of\s+(\d+)', total_pages_text, re.IGNORECASE)
                if match:
                    self._total_pages = int(match.group(1))
                    self.logger.info(f"📊 Found total pages: {self._total_pages}")
            
            # Also try to find the highest page number link
            if not self._total_pages:
                page_links = response.xpath("//a[contains(@class,'page') or contains(@href,'page')]/text()").getall()
                page_numbers = []
                for link_text in page_links:
                    # Extract numbers from text
                    numbers = re.findall(r'\d+', str(link_text))
                    page_numbers.extend([int(n) for n in numbers])
                if page_numbers:
                    self._total_pages = max(page_numbers)
                    self.logger.info(f"📊 Estimated total pages from page links: {self._total_pages}")
        
        # METHOD 2: Try multiple pagination selectors in order of reliability
        # SKIP METHOD 2 and METHOD 3 on high page numbers (>= 20) - they're unreliable and find wrong links
        # Always use METHOD 4 (manual construction) when on page 20+ for reliability
        if self._page_count < 20:
            next_page = (
                response.xpath("//a[@class='next' and @aria-label='Next Page']/@href").get()
                or response.xpath("//a[contains(@class,'next') and contains(@aria-label,'Next')]/@href").get()
                or response.xpath("//a[@class='next']/@href").get()
                or response.xpath("//a[contains(@class,'next')]/@href").get()
                or response.xpath("//a[@aria-label='Next Page']/@href").get()
                or response.xpath("//a[contains(@aria-label,'Next')]/@href").get()
                or response.xpath("//nav[@id='paging']//a[@class='next']/@href").get()
                or response.xpath("//nav[contains(@class,'pagination')]//a[@class='next']/@href").get()
            )
            
            # VALIDATE METHOD 2: Ensure "next" link points to a page number greater than current page
            # This prevents going backwards (e.g., from page 21 to page 2)
            if next_page:
                current_page_num = self._page_count
                # Extract page number from the "next" link
                page_match = re.search(r'[/?&](\d+)[/?]', next_page)
                if page_match:
                    next_page_num_from_link = int(page_match.group(1))
                    if next_page_num_from_link <= current_page_num:
                        # The "next" link points to an earlier or same page - invalid, use fallback
                        self.logger.warning(f"⚠️ METHOD 2 found 'next' link pointing to page {next_page_num_from_link} (current: {current_page_num}) - invalid, using fallback")
                        next_page = None
                    else:
                        self.logger.info(f"✅ METHOD 2 found valid 'next' link pointing to page {next_page_num_from_link}")
        else:
            # Skip METHOD 2 on high page numbers - use METHOD 4 instead
            next_page = None
            self.logger.info(f"⏭️ Skipping METHOD 2 (on page {self._page_count} >= 20, using METHOD 4 for reliability)")
        
        # METHOD 3: Fallback - Try to find page number links and get the next one
        # SKIP METHOD 3 on high page numbers - it's unreliable and finds wrong links
        if not next_page and self._page_count < 20:
            # Find all page number links
            page_number_links = response.xpath("//a[contains(@class,'page') or contains(@href,'page')]/@href").getall()
            current_page_num = self._page_count
            next_page_num = current_page_num + 1
            
            # IMPROVEMENT: Don't stop based on _total_pages alone - check for empty pages and target listings
            # Use website total as target if detected, otherwise default to at least 807 (website shows 807)
            min_target_listings = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
            if self._total_pages and next_page_num > self._total_pages + 15:
                # We're way past the expected total
                if self._consecutive_empty_pages >= 3 or (self._total_listings_found >= min_target_listings and self._consecutive_empty_pages >= 2):
                    self.logger.info(f"✅ Reached end (page {self._page_count} > expected {self._total_pages} + 15, and {self._consecutive_empty_pages} empty pages). Pagination complete!")
                    self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                    return
                elif self._total_listings_found < min_target_listings:
                    self.logger.warning(f"⚠️ Past expected pages but only {self._total_listings_found} listings (< {min_target_listings} target). Continuing...")
            
            # Try to find a link with the exact next page number (not substring match)
            # This prevents "20" from matching "/2/" or "/20/" incorrectly
            for link in page_number_links:
                if link:
                    # Extract page number from URL (e.g., /2/, /20/, ?page=2, ?page=20)
                    # Match patterns like /2/, /20/, ?page=2, &page=20
                    page_match = re.search(r'[/?&](\d+)[/?]', link)
                    if page_match:
                        link_page_num = int(page_match.group(1))
                        if link_page_num == next_page_num:  # Exact match, not substring
                            next_page = link
                            self.logger.info(f"🔍 Found next page via page number link: {next_page}")
                            break
        elif not next_page:
            # Skip METHOD 3 on high page numbers - use METHOD 4 instead
            self.logger.info(f"⏭️ Skipping METHOD 3 (on page {self._page_count} >= 20, using METHOD 4 for reliability)")
        
        # METHOD 4: Fallback - Construct page URL manually using page number
        if not next_page:
            # IMPROVEMENT: Always construct base URL from self.city to avoid typos
            # Don't rely on extracting from response URL which might have typos
            if not hasattr(self, '_base_url'):
                # Always use self.city to construct base URL
                # Remove trailing slash to avoid double slashes when appending page numbers
                self._base_url = f"https://www.apartments.com/{self.city}/for-rent-by-owner".rstrip('/')
                self.logger.info(f"📌 Constructed base URL for pagination: {self._base_url}")
            
            # IMPROVEMENT: Don't stop based on _total_pages alone - check for empty pages and target listings
            # Use website total as target if detected, otherwise default to at least 807 (website shows 807)
            min_target_listings = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
            next_page_num = self._page_count + 1
            if self._total_pages and next_page_num > self._total_pages + 15:
                # We're way past the expected total
                if self._consecutive_empty_pages >= 3 or (self._total_listings_found >= min_target_listings and self._consecutive_empty_pages >= 2):
                    self.logger.info(f"✅ Reached end (page {next_page_num} > expected {self._total_pages} + 15, and {self._consecutive_empty_pages} empty pages). Pagination complete!")
                    self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                    return
                elif self._total_listings_found < min_target_listings:
                    self.logger.warning(f"⚠️ Past expected pages but only {self._total_listings_found} listings (< {min_target_listings} target). Continuing...")
            
            # Construct next page URL - always use self.city to ensure correctness
            # Use path-based format: /{page_num}/ instead of ?page={page_num}
            # Normalize base_url to remove trailing slash to avoid double slashes
            base_url_clean = self._base_url.rstrip('/')
            next_page = f"{base_url_clean}/{next_page_num}/"
            
            # Ensure URL uses correct city (fix any typos in base_url)
            if f"/{self.city}/" not in next_page:
                # Replace any city in URL with self.city
                next_page = re.sub(r'/([a-z]+(?:-[a-z]+)+)/for-rent-by-owner', f'/{self.city}/for-rent-by-owner', next_page)
            
            # Also try alternative patterns
            if not next_page.startswith("https://www.apartments.com"):
                # Fallback: construct from city (always use self.city)
                # Use path-based format: /{page_num}/ instead of ?page={page_num}
                next_page = f"https://www.apartments.com/{self.city}/for-rent-by-owner/{next_page_num}/"
            
            self.logger.info(f"🔧 Constructed next page URL (fallback method): {next_page}")
        
        if next_page:
            next_page = next_page.strip()
            
            # Fix URL normalization issues
            # Handle "httpss://" typo and other malformed URLs
            if "httpss://" in next_page:
                next_page = next_page.replace("httpss://", "https://")
            elif "http://" in next_page and "https://" not in next_page:
                next_page = next_page.replace("http://", "https://")
            
            # Normalize relative URLs first
            if next_page.startswith("/"):
                next_page = "https://www.apartments.com" + next_page
            elif not next_page.startswith("http"):
                next_page = "https://www.apartments.com" + next_page
            
            # Ensure proper https:// prefix (fix any remaining issues)
            if not next_page.startswith("https://"):
                if next_page.startswith("http://"):
                    next_page = next_page.replace("http://", "https://", 1)
                else:
                    next_page = "https://" + next_page.lstrip("/")
            
            # Fix common URL typos: "apartmments" → "apartments", "apartments.coom" → "apartments.com"
            if "apartmments" in next_page:
                next_page = next_page.replace("apartmments", "apartments")
                self.logger.info(f"🔧 Fixed URL typo: apartmments → apartments")
            if "apartments.coom" in next_page:
                next_page = next_page.replace("apartments.coom", "apartments.com")
                self.logger.info(f"🔧 Fixed URL typo: apartments.coom → apartments.com")
            
            # FIX: Fix "for-rent-by-owner" typos in pagination URLs
            if "for-rent-by-oowner" in next_page:
                next_page = next_page.replace("for-rent-by-oowner", "for-rent-by-owner")
                self.logger.info(f"🔧 Fixed URL typo: for-rent-by-oowner → for-rent-by-owner")
            if "for-rent-by--owner" in next_page:
                next_page = next_page.replace("for-rent-by--owner", "for-rent-by-owner")
                self.logger.info(f"🔧 Fixed URL typo: for-rent-by--owner → for-rent-by-owner")
            if "for-rent-by-owwner" in next_page:
                next_page = next_page.replace("for-rent-by-owwner", "for-rent-by-owner")
                self.logger.info(f"🔧 Fixed URL typo: for-rent-by-owwner → for-rent-by-owner")
            # Fix any other double-letter/dash issues in "for-rent-by-owner"
            # This regex matches repeated 'o', '-', or 'w' characters
            next_page = re.sub(r'for-rent-by-([ow-])\1+owner', r'for-rent-by-owner', next_page)
            
            # Fix city name typos in URL (e.g., "chicagoo-il", "chicaago-il", "chiccago-il" → "chicago-il")
            # Always replace city in URL with self.city to ensure correctness
            url_city_match = re.search(r'/([a-z]+(?:-[a-z]+)+)/for-rent-by-owner', next_page)
            if url_city_match:
                url_city = url_city_match.group(1)
                if url_city != self.city:
                    # More robust typo detection: check if cities are similar
                    city_base = self.city.replace("-", "").lower()
                    url_city_base = url_city.replace("-", "").lower()
                    
                    # Method 1: Remove duplicate consecutive letters and compare
                    city_normalized = re.sub(r'(.)\1+', r'\1', city_base)
                    url_city_normalized = re.sub(r'(.)\1+', r'\1', url_city_base)
                    
                    # Method 2: Check if one contains the other (for partial matches)
                    # Method 3: Calculate similarity (simple Levenshtein-like check)
                    def simple_similarity(s1, s2):
                        """Simple similarity check - if >70% of characters match, consider similar"""
                        if not s1 or not s2:
                            return False
                        common = sum(1 for c in s1 if c in s2)
                        return common / max(len(s1), len(s2)) > 0.7
                    
                    # Replace if normalized match, contains match, or similarity match
                    should_replace = (
                        city_normalized == url_city_normalized or
                        city_base in url_city_base or url_city_base in city_base or
                        simple_similarity(city_base, url_city_base) or
                        # Also check if removing all duplicates from both gives same result
                        re.sub(r'(.)\1+', r'\1', city_base) == re.sub(r'(.)\1+', r'\1', url_city_base)
                    )
                    
                    if should_replace:
                        # Replace with correct city
                        next_page = re.sub(r'/([a-z]+(?:-[a-z]+)+)/for-rent-by-owner', f'/{self.city}/for-rent-by-owner', next_page)
                        self.logger.info(f"🔧 Fixed city typo in pagination URL: {url_city} → {self.city}")
                    else:
                        # Even if not similar, if it's in the URL path, replace it to be safe
                        # This handles cases where the URL has a completely wrong city
                        next_page = re.sub(r'/([a-z]+(?:-[a-z]+)+)/for-rent-by-owner', f'/{self.city}/for-rent-by-owner', next_page)
                        self.logger.info(f"🔧 Replaced city in URL with correct city: {url_city} → {self.city}")
            
            # Validate URL before following
            if next_page.startswith("https://www.apartments.com"):
                # IMPROVEMENT: More aggressive pagination - use website total as target if detected
                # Use actual website total if detected, otherwise default to at least 807 (website shows 807)
                min_target_listings = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
                
                if self._consecutive_empty_pages >= 6:
                    # 6+ consecutive empty pages - definitely at the end
                    self.logger.info(f"✅ Stopping pagination: {self._consecutive_empty_pages} consecutive empty pages")
                    self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                    return
                elif self._total_listings_found >= min_target_listings and self._consecutive_empty_pages >= 4:
                    # We have enough listings and 4+ empty pages - likely at the end
                    self.logger.info(f"✅ Stopping pagination: {self._total_listings_found} listings found (target: {min_target_listings}) and {self._consecutive_empty_pages} consecutive empty pages")
                    self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                    return
                elif self._total_listings_found < min_target_listings:
                    # We haven't reached target yet - continue even with many empty pages
                    if self._consecutive_empty_pages >= 5:
                        self.logger.warning(f"⚠️ {self._consecutive_empty_pages} consecutive empty pages, but only {self._total_listings_found} listings (< {min_target_listings} target). Continuing aggressively...")
                
                # Also check if we're way past expected total pages
                if self._total_pages and self._page_count >= self._total_pages + 15:
                    if self._consecutive_empty_pages >= 4:
                        self.logger.info(f"✅ Reached end (page {self._page_count} > expected {self._total_pages} + 15). Pagination complete!")
                        self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                        return
                    elif self._total_listings_found < min_target_listings:
                        self.logger.warning(f"⚠️ Past expected pages ({self._page_count} > {self._total_pages} + 15), but only {self._total_listings_found} listings (< {min_target_listings} target). Continuing aggressively...")
                
                self.logger.info(f"➡️  Following pagination to page {self._page_count + 1}: {next_page}")
                # Use dont_filter=True to allow revisiting pages (prevents duplicate filter from stopping scraper)
                yield response.follow(next_page, callback=self.parse_search, errback=self.handle_error, dont_filter=True)
            else:
                self.logger.warning(f"⚠️ Invalid pagination URL, skipping: {next_page}")
                # Always try fallback with correct city
                next_page_num = self._page_count + 1
                # Use path-based format: /{page_num}/ instead of ?page={page_num}
                fallback_url = f"https://www.apartments.com/{self.city}/for-rent-by-owner/{next_page_num}/"
                self.logger.info(f"🔄 Trying fallback URL: {fallback_url}")
                # Use dont_filter=True to allow revisiting pages
                yield response.follow(fallback_url, callback=self.parse_search, errback=self.handle_error, dont_filter=True)
        else:
            # No next page found - check if we should continue with fallback
            # IMPROVEMENT: More aggressive - use website total as target if detected
            # Ensure we target at least 807 (website shows 807 listings)
            min_target_listings = self._total_listings_on_site if self._total_listings_on_site else max(807, 1000)
            
            if self._consecutive_empty_pages >= 6:
                # 6+ consecutive empty pages - definitely at the end
                self.logger.info(f"✅ Stopping pagination: {self._consecutive_empty_pages} consecutive empty pages (no next link found)")
                self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
                if self._total_pages:
                    self.logger.info(f"📊 Total pages expected: {self._total_pages}, pages processed: {self._page_count}")
            elif self._total_listings_found >= min_target_listings and self._consecutive_empty_pages >= 4:
                # We have enough listings and 4+ empty pages - likely at the end
                self.logger.info(f"✅ Stopping pagination: {self._total_listings_found} listings found (target: {min_target_listings}) and {self._consecutive_empty_pages} consecutive empty pages (no next link found)")
                self.logger.info(f"📊 Processed {self._page_count} pages, found {self._total_listings_found} total listings")
            else:
                # Continue with fallback URL construction - we haven't reached target yet
                next_page_num = self._page_count + 1
                # Always use self.city to ensure correctness
                # Use path-based format: /{page_num}/ instead of ?page={page_num}
                fallback_url = f"https://www.apartments.com/{self.city}/for-rent-by-owner/{next_page_num}/"
                if self._total_listings_found < min_target_listings:
                    self.logger.info(f"🔄 No next link found, but only {self._total_listings_found} listings (< {min_target_listings} target). Continuing with fallback URL (empty pages: {self._consecutive_empty_pages}): {fallback_url}")
                else:
                    self.logger.info(f"🔄 No next link found, but continuing with fallback URL (empty pages: {self._consecutive_empty_pages}): {fallback_url}")
                # Use dont_filter=True to allow revisiting pages
                yield response.follow(fallback_url, callback=self.parse_search, errback=self.handle_error, dont_filter=True)
    
    def handle_error(self, failure):
        """Handle request errors gracefully and automatically skip blocked pages."""
        url = failure.request.url
        error_msg = str(failure.value) if failure.value else "Unknown error"
        self.logger.error(f"❌ Request failed: {url} - {error_msg}")
        
        # Initialize consecutive blocked pages counter if not exists
        if not hasattr(self, '_consecutive_blocked_pages'):
            self._consecutive_blocked_pages = 0
        
        # If it's a search page that failed, track failures and skip if needed
        # Support both ?page= format and /{page}/ format
        failed_page = None
        page_match = None
        
        # Try to extract page number from query parameter format (?page=)
        if '?page=' in url:
            page_match = re.search(r'[?&]page=(\d+)', url)
        # Try to extract page number from path format (/{page}/)
        elif '/for-rent-by-owner/' in url:
            # Match pattern like /for-rent-by-owner/5/ or /for-rent-by-owner/5
            page_match = re.search(r'/for-rent-by-owner/(\d+)/?$', url)
        
        if page_match:
            failed_page = int(page_match.group(1))
            
            # Check if this is a persistent error (520, timeout, etc.)
            is_persistent_error = (
                '520' in error_msg or 
                'Website Ban' in error_msg or
                'Timeout' in error_msg or
                'timeout' in error_msg.lower()
            )
            
            if is_persistent_error:
                # Increment consecutive blocked pages counter
                self._consecutive_blocked_pages += 1
                
                # If too many consecutive pages are blocked, stop to avoid infinite loop
                if self._consecutive_blocked_pages >= 10:
                    self.logger.error(
                        f"❌ STOPPING: {self._consecutive_blocked_pages} consecutive pages blocked. "
                        f"Website may be rate-limiting. Please wait and try again later."
                    )
                    self.logger.error(
                        f"💡 SUGGESTION: Wait 10-15 minutes before resuming, or try starting from page 1 "
                        f"with resume=true to skip duplicates."
                    )
                    return  # Stop the scraper - don't yield any more requests
                
                # Track failure count for this page
                if failed_page not in self._failed_pages:
                    self._failed_pages[failed_page] = 0
                self._failed_pages[failed_page] += 1
                failure_count = self._failed_pages[failed_page]
                
                # For persistent errors like 520, skip immediately on first failure
                should_skip = True
                
                if should_skip:
                    next_page = failed_page + 1
                    self.logger.warning(
                        f"⚠️ Page {failed_page} failed {failure_count} time(s) "
                        f"(error: {error_msg[:50]}). Automatically skipping to page {next_page} "
                        f"(Consecutive blocked: {self._consecutive_blocked_pages}/10)"
                    )
                    
                    # Construct skip URL using path-based format: /{page}/ instead of ?page=
                    skip_url = f"https://www.apartments.com/{self.city}/for-rent-by-owner/{next_page}/"
                    
                    # Yield request to continue from next page
                    yield scrapy.Request(
                        skip_url,
                        callback=self.parse_search,
                        errback=self.handle_error,
                        dont_filter=True,  # Allow duplicate URL if needed
                        meta={'skip_reason': f'Page {failed_page} blocked after {failure_count} failures'}
                    )
                    return
            else:
                # Reset consecutive blocked pages counter for non-persistent errors
                self._consecutive_blocked_pages = 0
                
                # Track failure count for this page
                if failed_page not in self._failed_pages:
                    self._failed_pages[failed_page] = 0
                self._failed_pages[failed_page] += 1
                failure_count = self._failed_pages[failed_page]
                
                # For other errors, skip after 2 failures
                should_skip = failure_count >= 2
                
                if should_skip:
                    next_page = failed_page + 1
                    self.logger.warning(
                        f"⚠️ Page {failed_page} failed {failure_count} time(s) "
                        f"(error: {error_msg[:50]}). Automatically skipping to page {next_page}"
                    )
                    
                    # Construct skip URL using path-based format: /{page}/ instead of ?page=
                    skip_url = f"https://www.apartments.com/{self.city}/for-rent-by-owner/{next_page}/"
                    
                    # Yield request to continue from next page
                    yield scrapy.Request(
                        skip_url,
                        callback=self.parse_search,
                        errback=self.handle_error,
                        dont_filter=True,  # Allow duplicate URL if needed
                        meta={'skip_reason': f'Page {failed_page} blocked after {failure_count} failures'}
                    )
                    return
        
        # Continue crawling even if some requests fail (but don't retry the same failed page)
    
    def _extract_from_json(self, response):
        """
        Extract listings from JSON-LD structured data (Schema.org format).
        Apartments.com provides bulk listing data in JSON-LD format.
        
        Returns:
            list: List of listing dictionaries with extracted data, or empty list if no JSON-LD found
        """
        self.logger.info("🔍 Starting JSON-LD bulk data extraction...")
        try:
            # Find JSON-LD script tags (type="application/ld+json")
            json_ld_scripts = response.xpath("//script[@type='application/ld+json']/text()").getall()
            self.logger.info(f"📜 Found {len(json_ld_scripts)} JSON-LD script tag(s)")
            
            if not json_ld_scripts:
                self.logger.warning("⚠️ No JSON-LD script tags found - falling back to HTML extraction")
                return []
            
            for idx, script_text in enumerate(json_ld_scripts, 1):
                self.logger.debug(f"📄 Processing JSON-LD script #{idx} ({len(script_text)} chars)")
                try:
                    # Parse JSON-LD
                    self.logger.debug(f"🔧 Parsing JSON-LD script #{idx}...")
                    json_ld_data = json.loads(script_text.strip())
                    self.logger.debug(f"✅ Successfully parsed JSON-LD script #{idx}")
                    
                    # Navigate to the ItemList structure
                    # Path: @graph -> CollectionPage -> mainEntity -> ItemList -> itemListElement
                    graph = json_ld_data.get('@graph', [])
                    if not graph:
                        # Sometimes JSON-LD is directly an array
                        if isinstance(json_ld_data, list):
                            graph = json_ld_data
                            self.logger.debug(f"📊 JSON-LD is directly an array with {len(graph)} items")
                        else:
                            self.logger.debug(f"⚠️ JSON-LD script #{idx}: No @graph found and not an array, skipping")
                            continue
                    else:
                        self.logger.debug(f"📊 Found @graph with {len(graph)} items")
                    
                    # Find CollectionPage with ItemList
                    item_list = None
                    collection_page_found = False
                    for item in graph:
                        if item.get('@type') == 'CollectionPage':
                            collection_page_found = True
                            self.logger.debug("✅ Found CollectionPage in @graph")
                            main_entity = item.get('mainEntity', {})
                            if main_entity.get('@type') == 'ItemList':
                                item_list = main_entity
                                self.logger.debug("✅ Found ItemList in CollectionPage.mainEntity")
                                break
                    
                    if not collection_page_found:
                        self.logger.debug(f"⚠️ JSON-LD script #{idx}: No CollectionPage found in @graph")
                        continue
                    
                    if not item_list:
                        self.logger.debug(f"⚠️ JSON-LD script #{idx}: CollectionPage found but no ItemList in mainEntity")
                        continue
                    
                    # Extract listings from itemListElement
                    listings = item_list.get('itemListElement', [])
                    if not listings:
                        self.logger.warning(f"⚠️ JSON-LD script #{idx}: ItemList found but itemListElement is empty")
                        continue
                    
                    total_items = item_list.get('numberOfItems', len(listings))
                    self.logger.info(f"✅ Found {len(listings)} listings in JSON-LD data (reported: {total_items} items)")
                    
                    # Convert JSON-LD listings to our format
                    self.logger.info(f"🔄 Converting {len(listings)} JSON-LD listings to internal format...")
                    extracted_listings = []
                    stats = {
                        'with_url': 0,
                        'with_phone': 0,
                        'with_address': 0,
                        'with_price': 0,
                        'with_title': 0,
                        'errors': 0
                    }
                    
                    for listing_idx, listing_item in enumerate(listings, 1):
                        try:
                            item_data = listing_item.get('item', {})
                            if not item_data:
                                stats['errors'] += 1
                                self.logger.debug(f"⚠️ Listing #{listing_idx}: No 'item' data found")
                                continue
                            
                            # Extract URL
                            url = item_data.get('url', '')
                            if not url:
                                stats['errors'] += 1
                                self.logger.debug(f"⚠️ Listing #{listing_idx}: No URL found")
                                continue
                            
                            stats['with_url'] += 1
                            
                            # Extract address from mainEntity
                            main_entity = item_data.get('mainEntity', {})
                            address_obj = main_entity.get('address', {})
                            
                            # Extract price from offers
                            offers = item_data.get('offers', {})
                            price = None
                            if offers:
                                if 'price' in offers:
                                    price = str(offers['price'])
                                    stats['with_price'] += 1
                                elif 'lowPrice' in offers and 'highPrice' in offers:
                                    low = offers.get('lowPrice', '')
                                    high = offers.get('highPrice', '')
                                    if low and high:
                                        price = f"${low} - ${high}"
                                        stats['with_price'] += 1
                                    elif low:
                                        price = f"${low}+"
                                        stats['with_price'] += 1
                            
                            # Check for phone
                            telephone = item_data.get('telephone', '')
                            if telephone:
                                stats['with_phone'] += 1
                            
                            # Check for title
                            title = item_data.get('name', '')
                            if title:
                                stats['with_title'] += 1
                            
                            # Check for address
                            if address_obj.get('streetAddress'):
                                stats['with_address'] += 1
                            
                            # Build listing dictionary
                            listing_dict = {
                                'url': url,
                                'title': title,
                                'description': item_data.get('description', ''),
                                'telephone': telephone,
                                'price': price or '',
                                'address': {
                                    'street': address_obj.get('streetAddress', ''),
                                    'city': address_obj.get('addressLocality', ''),
                                    'state': address_obj.get('addressRegion', ''),
                                    'zip': address_obj.get('postalCode', ''),
                                },
                                'geo': main_entity.get('geo', {}),
                            }
                            
                            extracted_listings.append(listing_dict)
                            
                            # Log first few listings for debugging
                            if listing_idx <= 3:
                                self.logger.debug(f"📋 Sample listing #{listing_idx}: {title[:50]}... | {price or 'No price'} | {telephone or 'No phone'}")
                            
                        except (KeyError, AttributeError, TypeError) as e:
                            stats['errors'] += 1
                            self.logger.debug(f"❌ Error extracting listing #{listing_idx} from JSON-LD: {e}")
                            continue
                    
                    if extracted_listings:
                        # Log statistics
                        self.logger.info(f"📊 JSON-LD Extraction Statistics:")
                        self.logger.info(f"   ✅ Total extracted: {len(extracted_listings)}/{len(listings)}")
                        self.logger.info(f"   📞 With phone: {stats['with_phone']} ({stats['with_phone']/len(extracted_listings)*100:.1f}%)")
                        self.logger.info(f"   🏠 With address: {stats['with_address']} ({stats['with_address']/len(extracted_listings)*100:.1f}%)")
                        self.logger.info(f"   💰 With price: {stats['with_price']} ({stats['with_price']/len(extracted_listings)*100:.1f}%)")
                        self.logger.info(f"   📝 With title: {stats['with_title']} ({stats['with_title']/len(extracted_listings)*100:.1f}%)")
                        if stats['errors'] > 0:
                            self.logger.warning(f"   ⚠️ Errors: {stats['errors']}")
                        self.logger.info(f"✅ Successfully extracted {len(extracted_listings)} listings from JSON-LD")
                        return extracted_listings
                    else:
                        self.logger.warning(f"⚠️ JSON-LD script #{idx}: Found {len(listings)} listings but couldn't extract any")
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"❌ JSON-LD script #{idx}: JSON decode error - {e}")
                    continue
                except (KeyError, AttributeError, TypeError) as e:
                    self.logger.warning(f"❌ JSON-LD script #{idx}: Structure navigation error - {e}")
                    continue
            
            # Fallback: Try to find __NEXT_DATA__ (Zillow pattern) - unlikely for Apartments.com
            self.logger.debug("🔍 Checking for __NEXT_DATA__ (Zillow pattern) as fallback...")
            next_data = response.css("script#__NEXT_DATA__::text").get()
            if next_data:
                self.logger.debug("✅ Found __NEXT_DATA__ script tag")
                try:
                    json_data = json.loads(next_data)
                    props = json_data.get('props', {})
                    page_props = props.get('pageProps', {})
                    listings = (
                        page_props.get('listings', []) or
                        page_props.get('searchResults', {}).get('listings', []) or
                        page_props.get('properties', [])
                    )
                    if listings:
                        self.logger.info(f"✅ Found {len(listings)} listings in __NEXT_DATA__")
                        return listings
                    else:
                        self.logger.debug("⚠️ __NEXT_DATA__ found but no listings in expected paths")
                except (json.JSONDecodeError, KeyError, AttributeError) as e:
                    self.logger.debug(f"⚠️ Could not parse __NEXT_DATA__: {e}")
            else:
                self.logger.debug("ℹ️ No __NEXT_DATA__ found (expected for Apartments.com)")
            
            self.logger.warning("⚠️ No JSON-LD data extracted - will fall back to HTML extraction")
            return []
            
        except Exception as e:
            self.logger.error(f"❌ Fatal error in JSON-LD extraction: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return []
    
    def sanitize_text(self, text):
        """Clean text to prevent JSON corruption from special characters."""
        if not text:
            return ""
        # Convert to string if not already
        text = str(text)
        # Remove problematic characters that break JSON
        text = text.replace('{', '').replace('}', '')
        # Replace newlines and carriage returns with spaces
        text = text.replace('\n', ' ').replace('\r', ' ')
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        # Remove multiple consecutive spaces
        text = ' '.join(text.split())
        return text.strip()
    
    def parse_detail(self, response):
        """
        Parse individual listing detail page and extract all required fields.
        IMPROVEMENT: Uses partial_item from meta if available (from search page extraction).
        """
        # IMPROVEMENT: Check for duplicate URLs
        if response.url in self.seen_urls and not response.meta.get('partial_item'):
            self.duplicate_count += 1
            self.logger.debug(f"⚠️ Skipping duplicate: {response.url}")
            return
        
        # DEBUG: Save first detail page HTML to inspect structure (optional, can be disabled)
        # Note: Debug files are automatically cleaned up when spider closes unless DEBUG_SAVE_HTML=True
        if not hasattr(self, '_first_detail_page_saved'):
            debug_enabled = self.crawler.settings.getbool("DEBUG_SAVE_HTML", False)
            if debug_enabled:
                with open('output/debug_detail_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info("Saved first detail page HTML to output/debug_detail_page.html")
            self._first_detail_page_saved = True
        
        # IMPROVEMENT: Start with partial item from search page if available (like Zillow)
        partial_item = response.meta.get('partial_item')
        if partial_item:
            item = partial_item
            self.logger.debug(f"📋 Using partial item data from search page for {response.url}")
        else:
            item = FrboListingItem()
        
        # Always update listing_url to ensure it's correct
        item["listing_url"] = response.url
        
        self.logger.debug(f"Extracting from: {response.url}")
        
        # IMPROVEMENT: Only extract fields that weren't already extracted from search page
        # Title / Property Name
        if not item.get("title"):
            title = (
                response.xpath("//h1[contains(@class,'propertyName')]/text()").get()
                or response.xpath("//h1/text()").get()
                or response.xpath("//h1//text()").getall()
            )
            if isinstance(title, list):
                title = " ".join(t.strip() for t in title if t.strip())
            item["title"] = self.sanitize_text(title)
        
        self.logger.debug(f"Title found: {item['title'][:50] if item.get('title') else 'EMPTY'}")
        
        # Price - Extract from JSON data first, then fallback to text
        if not item.get("price"):
            price = ""
            # Try to extract from JavaScript JSON data (most reliable)
            script_text = " ".join(response.xpath("//script[contains(text(), 'Rent')]/text()").getall())
            if script_text:
                rent_match = re.search(r'"Rent":(\d+(?:\.\d+)?)', script_text)
                if rent_match:
                    price = f"${int(float(rent_match.group(1)))}"
            
            # Fallback: Extract from rentDisplay and clean
            if not price:
                price_text = (
                    response.xpath("//span[contains(@class,'rentDisplay')]/text()").get()
                    or response.xpath("//div[contains(@class,'price')]//text()").getall()
                )
                if isinstance(price_text, list):
                    price_text = " ".join(t.strip() for t in price_text if t.strip())
                # Extract just the price (e.g., "$1,700" or "$1700")
                if price_text:
                    price_match = re.search(r'\$[\d,]+', price_text)
                    if price_match:
                        price = price_match.group(0)
                    else:
                        # Try to find first number that looks like a price
                        num_match = re.search(r'(\d{3,})', price_text)
                        if num_match:
                            price = f"${num_match.group(1)}"
            
            item["price"] = self.sanitize_text(price)
        
        # Beds/Baths/Sqft - Extract from JSON data first (most reliable)
        if not item.get("beds") or not item.get("baths"):
            beds = item.get("beds", "")
            baths = item.get("baths", "")
            sqft = item.get("sqft", "")
            
            script_text = " ".join(response.xpath("//script[contains(text(), 'Beds')]/text()").getall())
            
            if script_text:
                # Extract Beds
                if not beds:
                    beds_match = re.search(r'"Beds":(\d+)', script_text)
                    if beds_match:
                        beds = beds_match.group(1)
                
                # Extract Baths
                if not baths:
                    baths_match = re.search(r'"Baths":([\d.]+)', script_text)
                    if baths_match:
                        baths = str(int(float(baths_match.group(1))))  # Convert 1.0 to "1"
                
                # Extract SquareFeet
                if not sqft:
                    sqft_match = re.search(r'"SquareFeet":(\d+)', script_text)
                    if sqft_match:
                        sqft = sqft_match.group(1)
            
            # Fallback: Try XPath selectors
            if not beds:
                beds_text = (
                    response.xpath("//p[contains(@class,'rentInfoLabel') and contains(text(),'Bedroom')]/following-sibling::p/text()").get()
                    or response.xpath("//li[contains(@class,'beds')]//text()").getall()
                )
                if isinstance(beds_text, list):
                    beds_text = " ".join(t.strip() for t in beds_text if t.strip())
                if beds_text:
                    beds_match = re.search(r'(\d+)', beds_text)
                    if beds_match:
                        beds = beds_match.group(1)
            
            if not baths:
                baths_text = (
                    response.xpath("//p[contains(@class,'rentInfoLabel') and contains(text(),'Bathroom')]/following-sibling::p/text()").get()
                    or response.xpath("//li[contains(@class,'baths')]//text()").getall()
                )
                if isinstance(baths_text, list):
                    baths_text = " ".join(t.strip() for t in baths_text if t.strip())
                if baths_text:
                    baths_match = re.search(r'(\d+(?:\.\d+)?)', baths_text)
                    if baths_match:
                        baths = str(int(float(baths_match.group(1))))
            
            if not sqft:
                sqft_text = (
                    response.xpath("//p[contains(@class,'rentInfoLabel') and contains(text(),'Square Feet')]/following-sibling::p/text()").get()
                    or response.xpath("//li[contains(@class,'sqft')]//text()").getall()
                )
                if isinstance(sqft_text, list):
                    sqft_text = " ".join(t.strip() for t in sqft_text if t.strip())
                if sqft_text:
                    sqft_match = re.search(r'(\d{3,})', sqft_text)  # At least 3 digits for sqft
                    if sqft_match:
                        sqft = sqft_match.group(1)
            
            item["beds"] = self.sanitize_text(beds) if beds else item.get("beds", "")
            item["baths"] = self.sanitize_text(baths) if baths else item.get("baths", "")
            item["sqft"] = self.sanitize_text(sqft) if sqft else item.get("sqft", "")
        
        # Address parts - Improved extraction
        # Street address from h1 in delivery-address
        street = response.xpath("//div[contains(@class,'delivery-address')]//h1/text()").get()
        if not street:
            street = response.xpath("//div[contains(@class,'propertyAddress')]//h1/text()").get()
        street = self.sanitize_text(street) if street else ""
        
        # City from span after h2
        city = response.xpath("//div[contains(@class,'propertyAddressContainer')]//h2/span[1]/text()").get()
        if not city:
            city = response.xpath("//div[contains(@class,'propertyAddress')]//h2/span[1]/text()").get()
        city = self.sanitize_text(city) if city else ""
        
        # State from stateZipContainer
        state = response.xpath("//span[contains(@class,'stateZipContainer')]/span[1]/text()").get()
        if not state:
            state = response.xpath("//div[contains(@class,'propertyAddress')]//span[contains(@class,'state')]/text()").get()
        state = self.sanitize_text(state) if state else ""
        
        # Zip code from stateZipContainer (second span)
        zip_code = response.xpath("//span[contains(@class,'stateZipContainer')]/span[2]/text()").get()
        if not zip_code:
            zip_code = response.xpath("//div[contains(@class,'propertyAddress')]//span[contains(@class,'zip')]/text()").get()
        zip_code = self.sanitize_text(zip_code) if zip_code else ""
        
        # Build full address
        addr_parts = []
        if street:
            addr_parts.append(street)
        if city:
            addr_parts.append(city)
        if state:
            addr_parts.append(state)
        if zip_code:
            addr_parts.append(zip_code)
        
        item["full_address"] = ", ".join(addr_parts) if addr_parts else ""
        item["street"] = street
        item["city"] = city
        item["state"] = state
        item["zip_code"] = zip_code
        
        # Neighborhood
        neighborhood = (
            response.xpath("//div[contains(@class,'neighborhood')]//text()").get()
            or response.xpath("//a[contains(@class,'neighborhood')]//text()").get()
        )
        item["neighborhood"] = self.sanitize_text(neighborhood)
        
        # Owner / Manager Name
        owner_name = (
            response.xpath("//div[contains(@class,'contact-card')]//h2/text()").get()
            or response.xpath("//div[contains(@class,'contact-card')]//h3/text()").get()
            or response.xpath("//div[@id='contactCard']//h2/text()").get()
            or response.xpath("//div[@id='contactCard']//h3/text()").get()
            or response.xpath("//*[contains(., 'Managed by')]/following::strong[1]/text()").get()
            or response.xpath("//*[contains(., 'Contact')]//strong/text()").get()
        )
        item["owner_name"] = self.sanitize_text(owner_name)
        
        # Phone Numbers
        phone_numbers = []
        
        # Method 1: tel: links
        tel_links = response.xpath("//a[starts-with(@href, 'tel:')]/@href").getall()
        for tel in tel_links:
            phone = tel.replace("tel:", "").strip()
            if phone:
                phone_numbers.append(phone)
        
        # Method 2: Phone number text in specific elements
        phone_texts = response.xpath(
            "//*[contains(@class,'phone') or contains(@class,'call')]//text()"
        ).getall()
        for text in phone_texts:
            text = text.strip()
            if text and re.search(r'\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{4}', text):
                phone_numbers.append(text)
        
        # Method 3: Regex search in full page text (fallback)
        if not phone_numbers:
            full_text = " ".join(response.xpath("//text()").getall())
            matches = re.findall(
                r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}",
                full_text
            )
            for match in matches[:3]:  # Limit to first 3 matches
                if match:
                    phone_numbers.append(match)
        
        # Clean and deduplicate phone numbers
        cleaned_phones = []
        seen = set()
        for phone in phone_numbers:
            cleaned = re.sub(r'[^\d+]', '', phone)
            if len(re.sub(r'[^\d]', '', cleaned)) >= 10 and cleaned not in seen:
                seen.add(cleaned)
                cleaned_phones.append(cleaned)
        
        phone_str = ", ".join(cleaned_phones) if cleaned_phones else ""
        item["phone_numbers"] = self.sanitize_text(phone_str)
        
        # Email (only if exposed via mailto:)
        email = ""
        mailto_href = response.xpath("//a[starts-with(@href, 'mailto:')]/@href").get()
        if mailto_href:
            email = mailto_href.replace("mailto:", "").strip()
            if "?" in email:
                email = email.split("?", 1)[0]
        
        # Also check email input fields
        if not email:
            email_input = response.xpath("//input[@type='email']/@value").get()
            if email_input:
                email = email_input.strip()
        
        item["owner_email"] = self.sanitize_text(email)
        
        # Description
        desc_parts = response.xpath(
            "//section[contains(@class,'description')]//text()"
            " | //div[contains(@class,'descriptionSection')]//text()"
        ).getall()
        description = " ".join(t.strip() for t in desc_parts if t.strip())
        # Sanitize description (increased limit from 1000 to 5000 for more complete data)
        description = self.sanitize_text(description)
        item["description"] = description[:5000] if description else ""  # Increased limit
        
        # Log what we extracted
        fields_found = sum(1 for k, v in item.items() if v and str(v).strip())
        self.logger.info(f"✅ Extracted item from {response.url}: {fields_found}/{len(item)} fields populated")
        
        # Always yield the item - Scrapy will automatically save it to CSV incrementally
        # Even if some fields are empty, we still want the listing_url at minimum
        if item.get("listing_url"):
            yield item
            # Track items scraped
            if not hasattr(self, '_items_scraped'):
                self._items_scraped = 0
            self._items_scraped += 1
            # Log progress and CSV file updates
            if self._items_scraped == 1:
                self.logger.info(f"💾 CSV file created: {self.csv_filename}")
                self.logger.info(f"✅ First item saved to CSV: {fields_found}/{len(item)} fields populated")
            elif self._items_scraped % 10 == 0:
                self.logger.info(f"📊 Progress: {self._items_scraped} items scraped and saved to CSV...")
            else:
                self.logger.debug(f"💾 Item #{self._items_scraped} saved to CSV: {fields_found}/{len(item)} fields")
        else:
            self.logger.warning(f"⚠️ Skipping item - no listing_url: {response.url}")
        
        if fields_found == 0:
            self.logger.warning(f"⚠️ No data extracted from {response.url} - check output/debug_detail_page.html")
    
    def spider_closed(self, spider):
        """
        Cleanup method called when spider closes.
        Removes debug HTML files unless DEBUG_SAVE_HTML is explicitly enabled.
        IMPROVEMENT: Logs summary statistics including duplicates prevented.
        """
        # IMPROVEMENT: Log summary statistics (like Zillow scraper)
        total_found = getattr(self, '_total_listings_found', 0)
        items_scraped = getattr(self, '_items_scraped', 0)
        duplicates_skipped = getattr(self, 'duplicate_count', 0)
        pages_processed = getattr(self, '_page_count', 0)
        
        # Save final progress
        if self.progress_tracker:
            last_url = getattr(self, '_base_url', '')
            self.progress_tracker.save_progress(
                page_count=pages_processed,
                total_listings_found=total_found,
                last_url=last_url,
                items_scraped=items_scraped,
                consecutive_empty_pages=getattr(self, '_consecutive_empty_pages', 0)
            )
            self.logger.info(f"💾 Final progress saved to: {self.progress_tracker.progress_file}")
        
        self.logger.info("=" * 60)
        self.logger.info("📊 SCRAPING SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Pages processed: {pages_processed}")
        self.logger.info(f"✅ Total listings found: {total_found}")
        self.logger.info(f"✅ Items scraped: {items_scraped}")
        self.logger.info(f"🔄 Duplicates skipped: {duplicates_skipped}")
        if total_found > 0:
            efficiency = (items_scraped / total_found) * 100
            self.logger.info(f"📈 Scraping efficiency: {efficiency:.1f}%")
        self.logger.info("=" * 60)
        
        debug_enabled = self.crawler.settings.getbool("DEBUG_SAVE_HTML", False)
        if not debug_enabled:
            # Clean up debug files if they exist
            debug_files = [
                'output/debug_search_page.html',
                'output/debug_detail_page.html'
            ]
            for debug_file in debug_files:
                if os.path.exists(debug_file):
                    try:
                        os.remove(debug_file)
                        self.logger.debug(f"Cleaned up debug file: {debug_file}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove debug file {debug_file}: {e}")
        else:
            self.logger.info("Debug HTML files preserved (DEBUG_SAVE_HTML=True)")

