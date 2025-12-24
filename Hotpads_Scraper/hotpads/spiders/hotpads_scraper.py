import json
import pandas as pd
import scrapy
import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv
from scrapy.http import Request


class HotPadsSpider(scrapy.Spider):
    name = 'hotpads_scraper'
    MAX_KNOWN_HITS = 3
    _known_hits = 0
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 0,
        'RETRY_HTTP_CODES': [412, 404, 429, 520, 500, 502, 503, 504, 522, 524, 520],
        'FEEDS': {
            'output/Hotpads_Data.csv': {
                'format': 'csv', 
                'overwrite': True, 
                'encoding': 'utf-8',
                'fields': ['Name', 'Contact Name', 'Listing Time', 'Beds / Baths', 'Bedrooms', 'Bathrooms', 'Sqft', 'Phone Number', 'Address', 'Url', 'Price']
            }
        },
    }
    
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }

    def __init__(self, *args, **kwargs):
        super(HotPadsSpider, self).__init__(*args, **kwargs)
        self.locations_file = 'input/locations.csv'
        self.default_url = "https://hotpads.com/lincoln-park-chicago-il/for-rent-by-owner?border=false&isListedByOwner=true&lat=41.8919&listingTypes=rental&lon=-87.6612&z=12"
        # Check if user wants to use CSV instead
        self.use_csv = kwargs.get('use_csv', 'false').lower() == 'true'
        self._known_hits = 0
        self._first_listing_url = None
        
        # Initialize Supabase client
        try:
            project_root = Path(__file__).resolve().parents[2]
            env_path = project_root / '.env'
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
        except Exception:
            pass # Ignore errors, rely on system env vars
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            self.supabase = create_client(url, key)
            self.logger.info("Supabase client initialized for incremental check")
        else:
            self.supabase = None
            self.logger.warning("Supabase credentials not found, incremental check disabled")

    def start_requests(self):
        """Default: use hardcoded URL with filters. With use_csv=true: read from CSV"""
        if self.use_csv:
            # CSV mode: Read locations from CSV file
            try:
                df = pd.read_csv(self.locations_file)
                locations = df['location'].tolist()
                
                self.logger.info(f"CSV Mode: Found {len(locations)} location(s) to scrape")
                
                for location in locations:
                    # Format location for Hotpads URL (e.g., "chicago IL" -> "chicago-il")
                    formatted_location = location.strip().lower().replace(' ', '-')
                    
                    # Hotpads URL structure: https://hotpads.com/{location}/apartments-for-rent
                    url = f"https://hotpads.com/{formatted_location}/apartments-for-rent"
                    
                    self.logger.info(f"Starting scrape for: {location} ({url})")
                    
                    yield scrapy.Request(
                        url=url,
                        headers=self.headers,
                        callback=self.parse,
                        meta={
                            'zyte_api': {
                                "browserHtml": True,
                            },
                            'location': location
                        },
                        errback=self.errback_httpbin
                    )
            except FileNotFoundError:
                self.logger.error(f"Locations file not found: {self.locations_file}")
            except Exception as e:
                self.logger.error(f"Error reading locations file: {e}")
        else:
            # Default mode: Use hardcoded URL with filters
            self.logger.info(f"Default Mode: Starting scrape for provided URL: {self.default_url}")
            yield scrapy.Request(
                url=self.default_url,
                headers=self.headers,
                callback=self.parse,
                meta={
                    'zyte_api': {
                        "browserHtml": True,
                    },
                    'location': 'Lincoln Park - For Rent By Owner'
                },
                errback=self.errback_httpbin
            )

    def errback_httpbin(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure.request.url}")
        self.logger.error(f"Error: {repr(failure)}")


    def parse(self, response):
        self.logger.info(f"Parsing response from: {response.url}")
        
        listing_urls = []
        
        # Strategy 1: Try JSON-LD (Most Robust)
        try:
            json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
            for script in json_ld_scripts:
                try:
                    data = json.loads(script)
                    graph = data.get('@graph', []) if isinstance(data, dict) else []
                    
                    # Handle case where data is a list or single dict
                    if isinstance(data, list):
                        graph = data
                    elif isinstance(data, dict) and '@graph' not in data:
                        graph = [data]
                        
                    for item in graph:
                        if item.get('@type') == 'SearchResultsPage':
                            # Check mainEntity.itemListElement
                            if 'mainEntity' in item and 'itemListElement' in item['mainEntity']:
                                elements = item['mainEntity']['itemListElement']
                                self.logger.info(f"Found {len(elements)} items in JSON-LD mainEntity")
                                for el in elements:
                                    url = el.get('item', {}).get('url')
                                    if url: listing_urls.append(url)
                            
                            # Check direct itemListElement
                            elif 'itemListElement' in item:
                                elements = item['itemListElement']
                                self.logger.info(f"Found {len(elements)} items in JSON-LD itemListElement")
                                for el in elements:
                                    url = el.get('item', {}).get('url')
                                    if url: listing_urls.append(url)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            self.logger.error(f"Error parsing JSON-LD: {e}")

        # Strategy 2: XPath Selectors (Fallback)
        if not listing_urls:
            self.logger.info("JSON-LD yielded no URLs, trying XPath selectors...")
            
            # Try styles__li (verified in debug)
            records = response.xpath("//li[contains(@class, 'styles__li')]")
            if not records:
                records = response.xpath("//div[contains(@class, 'ListingCard')]")
            if not records:
                records = response.xpath("//li[.//a[contains(@href, '/chicago-il/') or contains(@href, '-il/')]]")

            self.logger.info(f"Found {len(records)} listing records via XPath")

            for record in records:
                url = record.xpath(".//a[contains(@href, '/')]//@href").get('')
                if not url:
                    url = record.xpath("./ancestor-or-self::a/@href").get('')
                if url:
                    listing_urls.append(url)

        # Remove duplicates
        listing_urls = list(set(listing_urls))
        self.logger.info(f"Total unique listing URLs found: {len(listing_urls)}")

        # Record first listing for state update (assuming newest)
        if not self._first_listing_url and listing_urls:
            first_url = listing_urls[0]
            self._first_listing_url = response.urljoin(first_url) if not first_url.startswith('http') else first_url

        # Bulk check existence in Supabase
        existing_urls = set()
        if self.supabase and listing_urls:
            try:
                # Hotpads uses 'url' field in Supabase (lowercase)
                response = self.supabase.table("hotpads_listings").select("url").in_("url", listing_urls).execute()
                existing_urls = {row['url'] for row in response.data}
                self.logger.info(f"Check results: {len(existing_urls)} listings already exist in database")
            except Exception as e:
                self.logger.error(f"Error checking Supabase existence: {e}")
        
        # Track consecutive empty pages to prevent infinite loops
        consecutive_empty = response.meta.get('consecutive_empty', 0)
        location = response.meta.get('location', 'unknown')
        if not listing_urls:
            consecutive_empty += 1
        else:
            consecutive_empty = 0
            
        if consecutive_empty >= 5:
            self.logger.info(f"Stopping pagination for {location}: 5 consecutive empty pages reached.")
            return

        for url in listing_urls:
            # Handle relative URLs
            full_url = response.urljoin(url) if not url.startswith('http') else url
            
            # Check existence
            if full_url in existing_urls:
                self._known_hits += 1
                self.logger.info(f"Listing already exists ({self._known_hits}/{self.MAX_KNOWN_HITS}): {full_url}")
                if self._known_hits >= self.MAX_KNOWN_HITS:
                    self.logger.info(f"Stopping: Reached {self.MAX_KNOWN_HITS} known listings.")
                    return # Stop processing this page and future pagination
                continue
            
            # Filter out non-listing URLs
            if '/apartments-for-rent' in full_url or 'map' in full_url:
                continue

            yield scrapy.Request(
                full_url,
                headers=self.headers,
                callback=self.parse_detail,
                meta={
                    'zyte_api': {
                        "browserHtml": True,
                    }
                }
            )

        # Next page selector
        next_page = response.xpath("//a[contains(@aria-label, 'Next') or contains(text(), 'Next')]/@href").get()
        if not next_page:
            next_page = response.xpath("//li[contains(@class, 'next')]//a/@href").get()
            
        if next_page:
            self.logger.info(f"Moving to next page: {next_page}")
            yield scrapy.Request(
                url=response.urljoin(next_page),
                headers=self.headers,
                callback=self.parse,
                meta={
                    'zyte_api': {
                        "browserHtml": True,
                    },
                    'consecutive_empty': consecutive_empty,
                    'location': location
                }
            )

    def parse_detail(self, response):
        item_url = response.url
        self.logger.info(f"📄 Parsing detail page: {item_url}")
        
        # Check for building pages (multi-unit)
        sub_records = response.xpath("//ul[@class='AreaListingsContainer-listings']/li")
        building_indicator = response.xpath("//article[contains(@class, 'BuildingArticleGroup')]").get()
        
        if sub_records or building_indicator or '/building' in item_url:
            self.logger.info(f"🏢 BUILDING PAGE DETECTED: {item_url}")
            self.logger.info(f"   - sub_records found: {len(sub_records)}")
            self.logger.info(f"   - building_indicator: {bool(building_indicator)}")
            self.logger.info(f"   - '/building' in URL: {'/building' in item_url}")
            
            # Extract individual unit URLs
            unit_urls = []
            for record in sub_records:
                url = record.xpath(".//a[@data-name='ListingCardAnchor']/@href").get('')
                if url:
                    unit_urls.append(url)
            
            # Fallback: try alternative selector
            if not unit_urls:
                unit_urls = response.xpath("//a[@data-name='ListingCardAnchor']/@href").getall()
                self.logger.info(f"   - Using fallback selector, found {len(unit_urls)} units")
            
            self.logger.info(f"   ✓ Extracting {len(unit_urls)} individual unit URLs")
            
            for url in unit_urls:
                full_url = response.urljoin(url)
                self.logger.info(f"      → Unit: {full_url}")
                yield scrapy.Request(
                        full_url,
                        headers=self.headers,
                        callback=self.parse_detail,
                        meta={
                            'zyte_api': {
                                "browserHtml": True,
                            }
                        }
                    )
            return
        
        # If we reach here, it's an individual listing page
        self.logger.info(f"🏠 INDIVIDUAL LISTING PAGE: {item_url}")
        
        # DEBUG: Save HTML for inspection (first page only)
        import os
        if not hasattr(self, '_debug_saved'):
            self._debug_saved = True
            with open('hotpads_debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.logger.info("✓ DEBUG: Saved HTML to hotpads_debug.html for inspection")

        # Initialize JSON-LD variables (will be populated first)
        jsonld_details = []
        jsonld_name = ''
        jsonld_phone = ''
        jsonld_address = ''
        jsonld_price = ''
        jsonld_sqft = ''
        jsonld_beds = ''
        jsonld_baths = ''
        jsonld_url = ''

        # STEP 1: Parse JSON-LD first (primary data source)
        script_content = response.xpath("//script[@type='application/ld+json']/text()").get()
        if script_content:
            try:
                data = json.loads(script_content)
                
                # Handle both dict and list data structures
                if isinstance(data, list):
                    jsonld_details = data
                elif isinstance(data, dict):
                    jsonld_details = data.get('@graph', [data])
                else:
                    jsonld_details = []
                
                # Extract JSON-LD values from first valid entry
                for detail in jsonld_details:
                    if not isinstance(detail, dict):
                        continue
                        
                    main_entity = detail.get('mainEntity', {})
                    
                    # Handle case where mainEntity is a list
                    if isinstance(main_entity, list):
                        main_entity = main_entity[0] if main_entity else {}

                    if not main_entity or not isinstance(main_entity, dict):
                        # Sometimes the detail itself is the main entity
                        main_entity = detail
                    
                    # Extract name
                    if not jsonld_name:
                        name_val = main_entity.get('name')
                        if name_val:
                            jsonld_name = name_val.strip() if isinstance(name_val, str) else str(name_val).strip()
                    
                    # Extract phone
                    if not jsonld_phone:
                        phone_val = main_entity.get('telephone')
                        if phone_val:
                            jsonld_phone = phone_val.strip() if isinstance(phone_val, str) else str(phone_val).strip()
                    
                    # Extract address
                    if not jsonld_address:
                        address_obj = main_entity.get('address', {})
                        if isinstance(address_obj, dict):
                            street_address = address_obj.get('streetAddress', '').strip()
                            address_locality = address_obj.get('addressLocality', '').strip()
                            address_region = address_obj.get('addressRegion', '').strip()
                            postal_code = address_obj.get('postalCode', '').strip()
                            full_addr = f"{street_address}, {address_locality}, {address_region} {postal_code}".strip(", ")
                            if full_addr:
                                jsonld_address = full_addr
                    
                    # Extract price - check both mainEntity and about object
                    if not jsonld_price:
                        # Try mainEntity first
                        offers = main_entity.get('offers', {})
                        if not offers or not isinstance(offers, dict):
                            # Try about object (ItemPage structure)
                            about = detail.get('about', {})
                            if isinstance(about, dict):
                                offers = about.get('offers', {})
                        
                        if isinstance(offers, dict):
                            price_val = offers.get('price')
                            if price_val:
                                jsonld_price = str(price_val).strip()
                            else:
                                low = offers.get('lowPrice')
                                high = offers.get('highPrice')
                                if low and high and low == high:
                                    jsonld_price = str(low)
                                elif low and high:
                                    jsonld_price = f"${low} - ${high}"
                                elif low:
                                    jsonld_price = str(low)
                                elif high:
                                    jsonld_price = str(high)
                    
                    # Extract sqft
                    if not jsonld_sqft:
                        floor_size = main_entity.get('floorSize', {})
                        if isinstance(floor_size, dict):
                            sqft_val = floor_size.get('value')
                            if sqft_val:
                                jsonld_sqft = str(sqft_val).strip()
                        elif isinstance(floor_size, str):
                            jsonld_sqft = floor_size.strip()
                    
                    # Extract beds - try explicit field first, then parse from description
                    if not jsonld_beds:
                        num_beds = main_entity.get('numberOfBedrooms') or main_entity.get('bedrooms')
                        if num_beds:
                            jsonld_beds = str(num_beds).strip()
                        else:
                            # Parse from description text (e.g., "2 bedroom, 1 bath")
                            description = main_entity.get('description', '')
                            if description and isinstance(description, str):
                                import re
                                bed_match = re.search(r'(\d+)\s*bedroom', description, re.IGNORECASE)
                                if bed_match:
                                    jsonld_beds = bed_match.group(1).strip()
                    
                    # Extract baths - try explicit field first, then parse from description
                    if not jsonld_baths:
                        num_baths = main_entity.get('numberOfBathroomsTotal') or main_entity.get('bathrooms') or main_entity.get('numberOfBathrooms')
                        if num_baths:
                            jsonld_baths = str(num_baths).strip()
                        else:
                            # Parse from description text (e.g., "2 bedroom, 1 bath")
                            description = main_entity.get('description', '')
                            if description and isinstance(description, str):
                                import re
                                bath_match = re.search(r'(\d+(?:\.\d+)?)\s*bath', description, re.IGNORECASE)
                                if bath_match:
                                    jsonld_baths = bath_match.group(1).strip()
                    
                    # Extract URL
                    if not jsonld_url:
                        url_val = main_entity.get('url')
                        if url_val:
                            jsonld_url = url_val.strip() if isinstance(url_val, str) else str(url_val).strip()
                    
                    # Break after first valid entry (we'll handle multiple entries in item creation)
                    break
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error on {response.url}: {e}")
            except Exception as e:
                self.logger.error(f"Error parsing JSON-LD on {response.url}: {e}")
        else:
            self.logger.warning(f"No JSON-LD script found on {response.url}")

        # STEP 2: XPath extraction (fallback only)
        # Extract Price with multiple fallback strategies
        xpath_price = response.xpath("//span[@data-test='listing-price']/text()").get('')
        self.logger.debug(f"Price selector 1: {xpath_price}")
        if not xpath_price:
            xpath_price = response.xpath("//div[contains(@class, 'Price')]/text()").get('')
            self.logger.debug(f"Price selector 2: {xpath_price}")
        if not xpath_price:
            xpath_price = response.xpath("//span[contains(@class, 'price')]/text()").get('')
            self.logger.debug(f"Price selector 3: {xpath_price}")
        if xpath_price:
            xpath_price = xpath_price.strip().replace('$', '').replace(',', '')
        else:
            xpath_price = ''
        self.logger.info(f"🏷️ EXTRACTED PRICE (XPath): '{xpath_price}'")
        
        # Improved XPath extraction for Beds, Baths, Sqft
        xpath_beds = ''
        xpath_baths = ''
        xpath_sqft = ''

        # Try multiple XPath strategies for bed/bath/sqft
        # Strategy 1: Look for specific data attributes
        xpath_beds = response.xpath("//span[@data-test='bed-count']/text()").get('')
        xpath_baths = response.xpath("//span[@data-test='bath-count']/text()").get('')
        xpath_sqft = response.xpath("//span[@data-test='sqft']/text()").get('')
        self.logger.debug(f"XPath beds/baths/sqft: {xpath_beds}/{xpath_baths}/{xpath_sqft}")
        
        # Strategy 2: Parse from text content - try multiple patterns
        if not xpath_beds or not xpath_baths or not xpath_sqft:
            # Get all text from the page for pattern matching
            summary_text = ' '.join(response.xpath("//div[contains(@class, 'PropertyInfo') or contains(@class, 'ListingDetails') or contains(@class, 'DetailedInfo')]//text()").getall())
            # Also try getting text from description areas
            if not summary_text or len(summary_text) < 50:
                summary_text = ' '.join(response.xpath("//*[contains(@class, 'description') or contains(@id, 'description')]//text()").getall())
            # Fallback to body text
            if not summary_text or len(summary_text) < 50:
                summary_text = ' '.join(response.xpath("//body//text()").getall())
            
            import re
            if not xpath_beds:
                # Try multiple patterns: "2 bed", "2 bedroom", "2 beds"
                bed_match = re.search(r'(\d+)\s*(?:bed|bedroom|beds)\b', summary_text, re.IGNORECASE)
                if bed_match:
                    xpath_beds = bed_match.group(1)
            
            if not xpath_baths:
                # Try multiple patterns: "1 bath", "1 bathroom", "1.5 bath"
                bath_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|bathroom|baths)\b', summary_text, re.IGNORECASE)
                if bath_match:
                    xpath_baths = bath_match.group(1)
            
            if not xpath_sqft:
                # Try multiple patterns: "1200 sqft", "1,200 sqft", "1200 sq ft", "1200 square feet"
                sqft_match = re.search(r'([\d,]+)\s*(?:sqft|sq\.?\s*ft\.?|square\s*feet?)\b', summary_text, re.IGNORECASE)
                if sqft_match:
                    xpath_sqft = sqft_match.group(1).replace(',', '')

        # Normalize XPath string values
        if xpath_beds:
            xpath_beds = xpath_beds.strip()
        if xpath_baths:
            xpath_baths = xpath_baths.strip()
        if xpath_sqft:
            xpath_sqft = xpath_sqft.strip()

        self.logger.info(f"🛏️ EXTRACTED (XPath): {xpath_beds} beds, {xpath_baths} baths, {xpath_sqft} sqft")

        # Extract contact info (XPath only, no JSON-LD equivalent)
        xpath_contact_name = response.xpath("//div[@class='ContactListedBy-name']/h2/text()[2]").get('')
        xpath_contact_name = xpath_contact_name.strip() if xpath_contact_name else ''
        
        # Try to extract contact company name (first text node in the same div)
        xpath_contact_company = response.xpath("//div[@class='ContactListedBy-name']/h2/text()[1]").get('')
        xpath_contact_company = xpath_contact_company.strip() if xpath_contact_company else ''
        
        # Try to extract email if available
        xpath_email = ''
        email_link = response.xpath("//a[contains(@href, 'mailto:')]/@href").get('')
        if email_link:
            xpath_email = email_link.replace('mailto:', '').strip()
        
        xpath_listing_time = response.xpath(
            "//li[@class='pb_2x pr_1x min-w_0 d_flex ai_flex-start gap_0']/span[contains(text(),'Listed')]/text()"
        ).get('')
        xpath_listing_time = xpath_listing_time.strip() if xpath_listing_time else ''

        # STEP 3: Create item(s) with priority logic (JSON-LD or XPath)
        items_yielded = False  # Track if we actually yielded any items
        
        # Use JSON-LD details if available, otherwise create single item
        if jsonld_details:
            # Create item for each JSON-LD detail entry
            for idx, detail in enumerate(jsonld_details):
                if not isinstance(detail, dict):
                    continue
                    
                main_entity = detail.get('mainEntity', {})
                
                # Handle case where mainEntity is a list
                if isinstance(main_entity, list):
                    main_entity = main_entity[0] if main_entity else {}

                if not main_entity or not isinstance(main_entity, dict):
                    # Sometimes the detail itself is the main entity
                    main_entity = detail
                
                # Extract values for this specific detail (override defaults if present)
                detail_name = ''
                detail_phone = ''
                detail_address = ''
                detail_price = ''
                detail_sqft = ''
                detail_beds = ''
                detail_baths = ''
                detail_url = ''
                
                # Extract name
                name_val = main_entity.get('name')
                if name_val:
                    detail_name = name_val.strip() if isinstance(name_val, str) else str(name_val).strip()
                
                # Extract phone
                phone_val = main_entity.get('telephone')
                if phone_val:
                    detail_phone = phone_val.strip() if isinstance(phone_val, str) else str(phone_val).strip()
                
                # Extract address
                address_obj = main_entity.get('address', {})
                if isinstance(address_obj, dict):
                    street_address = address_obj.get('streetAddress', '').strip()
                    address_locality = address_obj.get('addressLocality', '').strip()
                    address_region = address_obj.get('addressRegion', '').strip()
                    postal_code = address_obj.get('postalCode', '').strip()
                    full_addr = f"{street_address}, {address_locality}, {address_region} {postal_code}".strip(", ")
                    if full_addr:
                        detail_address = full_addr
                
                # Extract price - check both mainEntity and about object
                offers = main_entity.get('offers', {})
                if not offers or not isinstance(offers, dict):
                    # Try about object (ItemPage structure)
                    about = detail.get('about', {})
                    if isinstance(about, dict):
                        offers = about.get('offers', {})
                
                if isinstance(offers, dict):
                    price_val = offers.get('price')
                    if price_val:
                        detail_price = str(price_val).strip()
                    else:
                        low = offers.get('lowPrice')
                        high = offers.get('highPrice')
                        if low and high and low == high:
                            detail_price = str(low)
                        elif low and high:
                            detail_price = f"${low} - ${high}"
                        elif low:
                            detail_price = str(low)
                        elif high:
                            detail_price = str(high)
                
                # Extract sqft
                floor_size = main_entity.get('floorSize', {})
                if isinstance(floor_size, dict):
                    sqft_val = floor_size.get('value')
                    if sqft_val:
                        detail_sqft = str(sqft_val).strip()
                elif isinstance(floor_size, str):
                    detail_sqft = floor_size.strip()
                
                # Extract beds - try explicit field first, then parse from description
                num_beds = main_entity.get('numberOfBedrooms') or main_entity.get('bedrooms')
                if num_beds:
                    detail_beds = str(num_beds).strip()
                else:
                    # Parse from description text
                    description = main_entity.get('description', '')
                    if description and isinstance(description, str):
                        import re
                        bed_match = re.search(r'(\d+)\s*bedroom', description, re.IGNORECASE)
                        if bed_match:
                            detail_beds = bed_match.group(1).strip()
                
                # Extract baths - try explicit field first, then parse from description
                num_baths = main_entity.get('numberOfBathroomsTotal') or main_entity.get('bathrooms') or main_entity.get('numberOfBathrooms')
                if num_baths:
                    detail_baths = str(num_baths).strip()
                else:
                    # Parse from description text
                    description = main_entity.get('description', '')
                    if description and isinstance(description, str):
                        import re
                        bath_match = re.search(r'(\d+(?:\.\d+)?)\s*bath', description, re.IGNORECASE)
                        if bath_match:
                            detail_baths = bath_match.group(1).strip()
                
                # Extract URL
                url_val = main_entity.get('url')
                if url_val:
                    detail_url = url_val.strip() if isinstance(url_val, str) else str(url_val).strip()
                
                # Use detail-specific values or fall back to general JSON-LD or XPath
                final_name = detail_name or jsonld_name or ''
                final_phone = detail_phone or jsonld_phone or ''
                final_address = detail_address or jsonld_address or ''
                final_price = detail_price or jsonld_price or xpath_price or ''
                final_sqft = detail_sqft or jsonld_sqft or xpath_sqft or ''
                final_beds = detail_beds or jsonld_beds or xpath_beds or ''
                final_baths = detail_baths or jsonld_baths or xpath_baths or ''
                final_url = detail_url or jsonld_url or response.url
                
                # Generate unique URL if multiple details
                if len(jsonld_details) > 1:
                    try:
                        if final_url == response.url or final_url in [d.get('mainEntity', {}).get('url') if isinstance(d.get('mainEntity'), dict) else '' for d in jsonld_details if isinstance(d, dict)]:
                            final_url = f"{final_url}#index-{idx}"
                    except (ValueError, AttributeError):
                        pass
                
                # Build beds_bath string from final values
                parts = [val for val in [final_beds + ' beds' if final_beds else '', final_baths + ' baths' if final_baths else ''] if val]
                final_beds_bath = ", ".join(parts) if parts else ""
                
                # Create item with priority: JSON-LD or XPath
                item = {
                    'Name': final_name,
                    'Contact Name': xpath_contact_name,  # XPath only
                    'Contact Company': xpath_contact_company,  # XPath only
                    'Email': xpath_email,  # XPath only
                    'Listing Time': xpath_listing_time,  # XPath only
                    'Beds / Baths': final_beds_bath,
                    'Bedrooms': final_beds,
                    'Bathrooms': final_baths,
                    'Sqft': final_sqft,
                    'Phone Number': final_phone,
                    'Address': final_address,
                    'Url': final_url,
                    'Price': final_price if final_price else 'N/A'
                }
                
                # Log the scraped item
                self.logger.info(f"📍 Scraped: {final_name} | {final_address} | {final_beds}bd {final_baths}ba {final_sqft}sqft")
                
                yield item
                items_yielded = True  # Mark that we successfully created an item
        
        # If no items were yielded from JSON-LD, create item with XPath values only
        if not items_yielded:
            # Build beds_bath string from XPath values
            parts = [val for val in [xpath_beds + ' beds' if xpath_beds else '', xpath_baths + ' baths' if xpath_baths else ''] if val]
            final_beds_bath = ", ".join(parts) if parts else ""
            
            item = {
                'Name': '',  # No XPath equivalent
                'Contact Name': xpath_contact_name,
                'Contact Company': xpath_contact_company,
                'Email': xpath_email,
                'Listing Time': xpath_listing_time,
                'Beds / Baths': final_beds_bath,
                'Bedrooms': xpath_beds,
                'Bathrooms': xpath_baths,
                'Sqft': xpath_sqft,
                'Phone Number': '',  # No XPath equivalent
                'Address': '',  # No XPath equivalent
                'Url': response.url,
                'Price': xpath_price if xpath_price else 'N/A'
            }
            
            # Log the scraped item
            self.logger.info(f"📍 Scraped (XPath only): {xpath_beds}bd {xpath_baths}ba {xpath_sqft}sqft")
            
            yield item

    def closed(self, reason):
        """Update scrape_state table when spider finishes"""
        if self.supabase:
            try:
                state_data = {
                    "source_site": "hotpads",
                    "last_scraped_at": "now()",
                    "last_seen_url": self._first_listing_url,
                    "last_seen_id": None # Hotpads URLs usually contain IDs, but easier to keep as URL
                }
                self.supabase.table("scrape_state").upsert(state_data).execute()
                self.logger.info(f"Updated scrape_state for hotpads: {self._first_listing_url}")
            except Exception as e:
                self.logger.error(f"Error updating scrape_state: {e}")
