"""Main Zillow rental property spider - Refactored"""
import csv
import json
import logging
import os
import scrapy

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
        
        # Process each listing
        for home in homes_listing:
            detail_url = build_detail_url(home)
            meta = {'new_detailUrl': detail_url}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield response.follow(url=detail_url, callback=self.detail_page, meta=meta)

        # Handle pagination
        next_page = response.xpath("//a[@title='Next page']/@href").get('')
        if next_page:
            logger.info(f"ZIP {zipcode}: Found next page")
            meta = {'zipcode': zipcode}
            meta["zyte_api"] = {"browserHtml": True, "geolocation": "US"}
            yield scrapy.Request(response.urljoin(next_page), callback=self.parse, meta=meta)

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
            
            # Strict Filtering: Skip if not in Illinois
            addr = item.get('Address', '')
            if "IL" not in addr and "Illinois" not in addr:
                 logger.info(f"⛔ Skipping non-IL listing: {addr}")
                 return
            
            # Remove duplicates using ZPID if available, otherwise URL
            unique_id = zpid if zpid else item['Url']
            
            if unique_id not in self.unique_list:
                self.unique_list.append(unique_id)
                logger.info(f"SCRAPED: {item.get('Address', 'N/A')} | Price: {item.get('Asking Price', 'N/A')} | Agent: {item.get('Agent Name', 'N/A')}")
                yield item
                
        except Exception as e:
            logger.error(f"Error in parse_agent_info: {e}", exc_info=True)
