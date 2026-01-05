import csv
import json
import logging
import os
import re
import scrapy
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# Import configuration and utilities
from .trulia_config import (
    HEADERS, OUTPUT_FIELDS, 
    RETRY_TIMES, DOWNLOAD_DELAY, AGENT_INFO_URL
)
from .trulia_parsers import TruliaJSONParser
from ..utils.url_builder import build_rental_url, build_detail_url

logger = logging.getLogger(__name__)


class TruliaSpider(scrapy.Spider):
    """Spider for scraping Trulia FSBO property listings"""
    
    name = "trulia_spider"
    unique_list = []
    MAX_KNOWN_HITS = 3
    _known_hits = 0
    
    def __init__(self, *args, **kwargs):
        super(TruliaSpider, self).__init__(*args, **kwargs)
        self._known_hits = 0
        self._first_listing_url = None
        self._first_listing_id = None
        
        # Initialize Supabase client
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
        'RETRY_TIMES': RETRY_TIMES,
        'DOWNLOAD_DELAY': DOWNLOAD_DELAY,
    }

    def read_input_file(self):
        """Read locations from input/input.csv"""
        input_file_path = os.path.join(self.project_root, 'input', 'input.csv')
        
        if not os.path.exists(input_file_path):
            logger.error(f"Input file not found at {input_file_path}")
            return []

        with open(input_file_path, 'r') as rfile:
            data = list(csv.DictReader(rfile))
            logger.info(f"Loaded {len(data)} locations from input file")
            return data

    def start_requests(self):
        """Generate initial requests for each location or URL"""
        # Check for URL parameter (from URL-based extraction) or start_url (legacy) or env var
        direct_url = getattr(self, 'url', None) or getattr(self, 'start_url', None) or os.getenv('TRULIA_FRBO_URL')
        if direct_url:
            logger.info(f"Using Direct URL: {direct_url}")
            # When URL is provided, disable early stopping (set MAX_KNOWN_HITS to very high value)
            # This allows scraping all pages even if some listings already exist
            self.MAX_KNOWN_HITS = 999999
            meta = {'zipcode': 'Direct URL', 'url_provided': True}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield scrapy.Request(url=direct_url, headers=HEADERS, meta=meta, dont_filter=True)
            return

        file_data = self.read_input_file()
        if not file_data:
            logger.warning("No input file found and no URL provided. Spider will not scrape anything.")
            return
        try:
            for each_row in file_data:
                custom_url = each_row.get('url', '').strip()
                location = each_row.get('location', '').strip() or each_row.get('zipcode', '').strip()
                
                if custom_url:
                    final_url = custom_url
                    current_location = "Custom URL" 
                    logger.info(f"Starting request for Custom URL")
                elif location:
                    final_url = build_rental_url(location)
                    current_location = location
                    logger.info(f"Starting request for Location: {location}")
                else:
                    continue
                
                meta = {'zipcode': current_location}
                meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
                    
                yield scrapy.Request(url=final_url, headers=HEADERS, meta=meta, dont_filter=True)
                
        except Exception as e:
            logger.error(f"Error in start_requests: {e}", exc_info=True)

    def parse(self, response, **kwargs):
        """Parse search results page"""
        zipcode = response.meta.get('zipcode', 'unknown')
        logger.info(f"Parsing response for location: {zipcode}, Status: {response.status}")
        
        homes_listing = TruliaJSONParser.extract_listings(response, zipcode)
        
        # Record first listing for state update (assuming newest)
        if not self._first_listing_url and homes_listing:
            first = homes_listing[0]
            self._first_listing_url = build_detail_url(first)
            self._first_listing_id = first.get('id', '')
        
        consecutive_empty = response.meta.get('consecutive_empty', 0)
        if not homes_listing:
            consecutive_empty += 1
        else:
            consecutive_empty = 0
            
        if consecutive_empty >= 5:
            logger.info(f"Stopping pagination for {zipcode}: 5 consecutive empty pages reached.")
            return
        
        listing_urls = [build_detail_url(home) for home in homes_listing if build_detail_url(home)]
        
        existing_urls = set()
        if self.supabase and listing_urls:
            try:
                # Use listing_link as used in the pipeline/table
                response_db = self.supabase.table("trulia_listings").select("listing_link").in_("listing_link", listing_urls).execute()
                existing_urls = {row['listing_link'] for row in response_db.data}
                logger.info(f"Check results: {len(existing_urls)} listings already exist in database")
            except Exception as e:
                logger.error(f"Error checking Supabase existence: {e}")

        for home in homes_listing:
            detail_url = build_detail_url(home)
            if not detail_url:
                continue
            
            if detail_url in existing_urls:
                self._known_hits += 1
                logger.info(f"Listing already exists ({self._known_hits}/{self.MAX_KNOWN_HITS}): {detail_url}")
                # Only stop early if URL was NOT provided (default behavior for batch scraping)
                # When URL is provided, continue scraping all pages even if some listings exist
                url_provided = response.meta.get('url_provided', False)
                if not url_provided and self._known_hits >= self.MAX_KNOWN_HITS:
                    logger.info(f"Stopping: Reached {self.MAX_KNOWN_HITS} known listings.")
                    return
                continue

            home_data = home.get('homeData', {})
            meta = {
                'new_detailUrl': detail_url,
                'homeData': home_data
            }
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield response.follow(url=detail_url, headers=HEADERS, callback=self.detail_page, meta=meta)

        next_page = response.xpath("//a[contains(@aria-label, 'Next') or contains(text(), 'Next')]/@href").get('')
        if not next_page:
            next_page = response.xpath("//a[@data-testid='pagination-next']/@href").get('')
        
        if next_page:
            logger.info(f"Location {zipcode}: Found next page")
            meta = {'zipcode': zipcode, 'consecutive_empty': consecutive_empty, 'url_provided': response.meta.get('url_provided', False)}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield scrapy.Request(response.urljoin(next_page), headers=HEADERS, callback=self.parse, meta=meta, dont_filter=True)

    def detail_page(self, response):
        """Parse property detail page"""
        try:
            home_data = response.meta.get('homeData', {})
            item, property_id, beds_bath = TruliaJSONParser.extract_property_details(response, home_data)
            
            if not property_id:
                logger.warning(f"No property ID found for {response.url}")
            
            payload = TruliaJSONParser.build_agent_payload(property_id) if property_id else {}
            meta = {'item': item, 'beds_bath': beds_bath, 'property_id': property_id}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            
            if AGENT_INFO_URL and property_id:
                yield scrapy.Request(
                    url=AGENT_INFO_URL,
                    method='POST',
                    body=json.dumps(payload),
                    headers=HEADERS,
                    callback=self.parse_agent_info,
                    meta=meta,
                    dont_filter=True
                )
            else:
                item['Beds / Baths'] = beds_bath
                item['zpid'] = property_id or ''
                final_item = self._finalize_item(item)
                if final_item:
                    yield final_item

        except Exception as e:
            logger.error(f"Error in detail_page: {e}", exc_info=True)

    def parse_agent_info(self, response):
        """Parse agent information from API response"""
        try:
            item = response.meta['item']
            beds_bath = response.meta['beds_bath']
            property_id = response.meta.get('property_id')
            
            agent_data = json.loads(response.text)
            agentInfo = agent_data.get('propertyInfo', {}).get('agentInfo', {}) or agent_data.get('agentInfo', {})

            item['Name'] = agentInfo.get('businessName', '') or agentInfo.get('name', '')
            item['Beds / Baths'] = beds_bath
            item['Phone Number'] = agentInfo.get('phoneNumber', '') or agentInfo.get('phone', '')
            item['Agent Name'] = agentInfo.get('displayName', '') or agentInfo.get('agentName', '')
            item['zpid'] = property_id or ''
            
            final_item = self._finalize_item(item)
            if final_item:
                yield final_item
                
        except Exception as e:
            logger.error(f"Error in parse_agent_info: {e}", exc_info=True)
    
    def _finalize_item(self, item):
        """Finalize item before yielding"""
        if 'Address' in item and item['Address']:
             item['Address'] = " ".join(str(item['Address']).split())
        
        # Removed Illinois-only filter to support any location
        # (Previously filtered for IL only: if "IL" not in addr and "Illinois" not in addr: return None)
        
        unique_id = item.get('zpid') or item.get('Url', '')
        
        if unique_id not in self.unique_list:
            self.unique_list.append(unique_id)
            logger.info(f"SCRAPED: {item.get('Address', 'N/A')} | Price: {item.get('Asking Price', 'N/A')} | Agent: {item.get('Agent Name', 'N/A')}")
            return item
        
        return None

    def closed(self, reason):
        """Update scrape_state table when spider finishes"""
        if self.supabase:
            try:
                state_data = {
                    "source_site": "trulia",
                    "last_scraped_at": "now()",
                    "last_seen_url": self._first_listing_url,
                    "last_seen_id": str(self._first_listing_id) if self._first_listing_id else None
                }
                self.supabase.table("scrape_state").upsert(state_data).execute()
                logger.info(f"Updated scrape_state for trulia: {self._first_listing_url}")
            except Exception as e:
                logger.error(f"Error updating scrape_state: {e}")