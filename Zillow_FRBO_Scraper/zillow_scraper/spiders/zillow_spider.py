"""Main Zillow rental property spider - Refactored"""
import csv
import json
import logging
import os
import scrapy
from urllib.parse import urljoin

from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Import configuration and utilities
from .zillow_config import (
    ZYTE_PROXY, HEADERS, OUTPUT_FIELDS, 
    RETRY_TIMES, DOWNLOAD_DELAY, AGENT_INFO_URL
)
from .zillow_parsers import ZillowJSONParser
from ..utils.url_builder import build_rental_url, build_detail_url

logger = logging.getLogger(__name__)


class ZillowSpiderSpider(scrapy.Spider):
    """Spider for scraping Zillow rental property listings"""
    
    name = "zillow_spider"
    unique_list = []
    MAX_KNOWN_HITS = 3
    _known_hits = 0
    
    def __init__(self, *args, **kwargs):
        super(ZillowSpiderSpider, self).__init__(*args, **kwargs)
        self._known_hits = 0
        self._first_listing_url = None
        self._first_listing_zpid = None
        
        # Initialize Supabase client
        # Go up: spiders -> zillow_scraper -> Zillow_FRBO_Scraper -> Scraper_backend
        project_root_env = Path(__file__).resolve().parents[3] 
        env_path = project_root_env / '.env'
        load_dotenv(dotenv_path=env_path)
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if url and key:
            self.supabase = create_client(url, key)
            logger.info("Supabase client initialized for incremental check")
        else:
            self.supabase = None
            logger.warning("Supabase credentials not found, incremental check disabled")

    # Get absolute path to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'FEEDS': {
            os.path.join(project_root, 'output', 'Zillow_Data.csv'): {
                'format': 'csv',
                'overwrite': True,
                'encoding': 'utf-8',
                'fields': OUTPUT_FIELDS,
            }
        },
        'RETRY_TIMES': RETRY_TIMES,
        'DOWNLOAD_DELAY': DOWNLOAD_DELAY,
    }

    def read_input_file(self):
        """Read ZIP codes from input/input.csv"""
        input_file_path = os.path.join(self.project_root, 'input', 'input.csv')
        
        if not os.path.exists(input_file_path):
            logger.error(f"Input file not found at {input_file_path}")
            return []

        with open(input_file_path, 'r') as rfile:
            data = list(csv.DictReader(rfile))
            logger.info(f"Loaded {len(data)} ZIP codes from input file")
            return data

    def start_requests(self):
        """Generate initial requests for each ZIP code or URL"""
        # Check for direct URL from argument or environment variable
        direct_url = getattr(self, 'start_url', None) or os.getenv('ZILLOW_FRBO_URL')
        if direct_url:
            logger.info(f"Using Direct URL: {direct_url}")
            meta = {'zipcode': 'Direct URL'}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield scrapy.Request(url=direct_url, meta=meta)
            return

        file_data = self.read_input_file()
        try:
            for each_row in file_data:
                # Check for direct URL first
                custom_url = each_row.get('url', '').strip()
                zipcode = each_row.get('zipcode', '').strip()
                
                if custom_url:
                    final_url = custom_url
                    # Use a placeholder or extract from URL if needed, but 'Custom URL' is safe for logging
                    current_zip = "Custom URL" 
                    logger.info(f"Starting request for Custom URL")
                elif zipcode:
                    final_url = build_rental_url(zipcode)
                    current_zip = zipcode
                    logger.info(f"Starting request for ZIP: {zipcode}")
                else:
                    continue
                
                meta = {'zipcode': current_zip}
                meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
                    
                yield scrapy.Request(url=final_url, meta=meta)
                
        except Exception as e:
            logger.error(f"Error in start_requests: {e}", exc_info=True)

    def parse(self, response, **kwargs):
        """Parse search results page"""
        zipcode = response.meta.get('zipcode', 'unknown')
        logger.info(f"Parsing response for ZIP: {zipcode}")
        
        # Use parser utility to extract listings
        homes_listing = ZillowJSONParser.extract_listings(response, zipcode)
        
        # Track consecutive empty pages to prevent infinite loops
        consecutive_empty = response.meta.get('consecutive_empty', 0)
        if not homes_listing:
            consecutive_empty += 1
        else:
            consecutive_empty = 0
            
        # Record first listing for state update (assuming newest)
        if not self._first_listing_url and homes_listing:
            first = homes_listing[0]
            self._first_listing_url = build_detail_url(first)
            self._first_listing_zpid = first.get('zpid', '') or first.get('id', '')
            
        if consecutive_empty >= 5:
            logger.info(f"Stopping pagination for {zipcode}: 5 consecutive empty pages reached.")
            return
        
        # Prepare URLs for bulk check
        listing_urls = [build_detail_url(home) for home in homes_listing]
        
        # Bulk check existence in Supabase
        existing_urls = set()
        if self.supabase and listing_urls:
            try:
                # Use zillow_frbo_listings for FRBO scraper
                response = self.supabase.table("zillow_frbo_listings").select("url").in_("url", listing_urls).execute()
                existing_urls = {row['url'] for row in response.data}
                logger.info(f"Check results: {len(existing_urls)} listings already exist in database")
            except Exception as e:
                logger.error(f"Error checking Supabase existence: {e}")

        # Process each listing
        for home in homes_listing:
            detail_url = build_detail_url(home)
            
            if detail_url in existing_urls:
                self._known_hits += 1
                logger.info(f"Listing already exists (count: {self._known_hits}): {detail_url}")
                # Continue processing - don't stop early, scrape all listings
                continue

            meta = {'new_detailUrl': detail_url}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            # build_detail_url already returns absolute URLs, so use it directly
            # response.urljoin() doesn't work with Zyte API responses, so we use the URL directly
            yield scrapy.Request(url=detail_url, callback=self.detail_page, meta=meta)

        # Handle pagination
        next_page = response.xpath("//a[@title='Next page']/@href").get('')
        if next_page:
            logger.info(f"ZIP {zipcode}: Found next page")
            meta = {'zipcode': zipcode, 'consecutive_empty': consecutive_empty}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            # Use urllib.parse.urljoin since response.urljoin() doesn't work with Zyte API responses
            base_url = getattr(response, 'url', 'https://www.zillow.com')
            next_page_url = urljoin(base_url, next_page)
            yield scrapy.Request(next_page_url, callback=self.parse, meta=meta)

    def detail_page(self, response):
        """Parse property detail page"""
        try:
            # Use parser utility to extract property details
            item, zpid, beds_bath = ZillowJSONParser.extract_property_details(response)
            
            if not zpid:
                logger.warning(f"No ZPID found for {response.url}")
                return
            
            # Build payload for agent info request
            payload = ZillowJSONParser.build_agent_payload(zpid)
            
            # Request agent information
            meta = {'item': item, 'beds_bath': beds_bath, 'zpid': zpid}
            if ZYTE_PROXY:
                meta['proxy'] = ZYTE_PROXY
                
            yield scrapy.Request(
                url=AGENT_INFO_URL,
                method='POST',
                body=json.dumps(payload),
                headers=HEADERS,
                callback=self.parse_agent_info,
                meta=meta,
                dont_filter=True
            )

        except Exception as e:
            logger.error(f"Error in detail_page: {e}", exc_info=True)

    def parse_agent_info(self, response):
        """Parse agent information from API response"""
        try:
            item = response.meta['item']
            beds_bath = response.meta['beds_bath']
            zpid = response.meta.get('zpid')
            
            agent_json = response.text
            agent_data = json.loads(agent_json)
            agentInfo = agent_data.get('propertyInfo', {}).get('agentInfo', {})

            item['Name'] = agentInfo.get('businessName', '')
            item['Beds / Baths'] = beds_bath
            item['Phone Number'] = agentInfo.get('phoneNumber', '')
            item['Agent Name'] = agentInfo.get('displayName', '')
            item['zpid'] = zpid  # Add zpid to item for Supabase pipeline
            
            # Normalize whitespace in Address
            if 'Address' in item and item['Address']:
                 item['Address'] = " ".join(str(item['Address']).split())
            
            # Removed Illinois-only filter to support any location
            # (Previously filtered for IL only)
            
            # Remove duplicates using ZPID if available, otherwise URL
            unique_id = zpid if zpid else item['Url']
            
            if unique_id not in self.unique_list:
                self.unique_list.append(unique_id)
                logger.info(f"SCRAPED: {item.get('Address', 'N/A')} | Price: {item.get('Asking Price', 'N/A')} | Agent: {item.get('Agent Name', 'N/A')}")
                yield item
                
        except Exception as e:
            logger.error(f"Error in parse_agent_info: {e}", exc_info=True)

    def closed(self, reason):
        """Update scrape_state table when spider finishes"""
        if self.supabase:
            try:
                state_data = {
                    "source_site": "zillow_frbo",
                    "last_scraped_at": "now()",
                    "last_seen_url": self._first_listing_url,
                    "last_seen_id": str(self._first_listing_zpid) if self._first_listing_zpid else None
                }
                self.supabase.table("scrape_state").upsert(state_data).execute()
                logger.info(f"Updated scrape_state for zillow_frbo: {self._first_listing_url}")
            except Exception as e:
                logger.error(f"Error updating scrape_state: {e}")
