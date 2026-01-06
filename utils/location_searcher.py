"""
Location Search Utilities
Searches platforms to get the actual listing URL from a location name
"""

import re
import requests
from typing import Optional, Dict, Tuple
from urllib.parse import quote, urljoin
import logging
from utils.url_detector import URLDetector

logger = logging.getLogger(__name__)

class LocationSearcher:
    """Search platforms for location and return the actual listing URL"""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    @classmethod
    def search_trulia(cls, location: str) -> Optional[str]:
        """
        Search Trulia for a location and return the actual listing URL.
        
        Strategy:
        1. Try accessing the search page with the location query
        2. Look for redirect or the actual listing page URL
        3. Check if it's a valid listing page
        """
        try:
            # Trulia's search endpoint - try different formats
            location_clean = location.strip()
            
            # Try direct access to /{state}/{city}/ format first
            # We need to parse the location to get state and city
            # But first, let's try searching via their autocomplete/search API
            
            # Format 1: Try location as-is (expecting "City, State" or "City State")
            # Trulia uses format like: trulia.com/MN/Minneapolis/
            # We'll try to construct it and validate
            
            # For now, let's try accessing the search results page directly
            # Trulia search: https://www.trulia.com/search/{location}/
            search_url = f"https://www.trulia.com/search/{quote(location_clean)}/"
            
            logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
            logger.info(f"[LocationSearcher] Trying URL: {search_url}")
            
            # Make a HEAD request to check redirect
            try:
                response = requests.head(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Final URL after redirect: {final_url}")
                
                # Check if it's a valid listing page
                if 'trulia.com' in final_url and ('/MN/' in final_url or '/IL/' in final_url or any(f'/{state}/' in final_url for state in ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'])):
                    # It's a location page, now append for_sale filter
                    # Format: /MN/Minneapolis/ -> /for_sale/MN/Minneapolis/
                    if '/for_sale/' not in final_url:
                        # Extract state and city from URL like /MN/Minneapolis/
                        match = re.search(r'/([A-Z]{2})/([^/]+)/?$', final_url)
                        if match:
                            state = match.group(1)
                            city = match.group(2)
                            # Build the for_sale URL
                            listing_url = f"https://www.trulia.com/for_sale/{state}/{city}/SINGLE-FAMILY_HOME_type/"
                            logger.info(f"[LocationSearcher] Built listing URL: {listing_url}")
                            return listing_url
                    
                    # If it already has for_sale, check if we need to add property type
                    if '/for_sale/' in final_url and '/SINGLE-FAMILY_HOME_type/' not in final_url:
                        return f"{final_url.rstrip('/')}/SINGLE-FAMILY_HOME_type/"
                    
                    return final_url
                    
            except Exception as e:
                logger.warning(f"[LocationSearcher] HEAD request failed: {e}, trying GET")
            
            # Fallback: Try GET request
            try:
                response = requests.get(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                # Parse HTML to find the actual listing link
                html = response.text
                
                # Look for patterns in the HTML that indicate listing URLs
                # Trulia uses patterns like /for_sale/{state}/{city}/ or /MN/Minneapolis/
                patterns = [
                    r'href="(/for_sale/[^"]+)"',
                    r'href="(/([A-Z]{2})/[^/]+/)"',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, html)
                    if matches:
                        # Take the first match
                        path = matches[0] if isinstance(matches[0], str) else matches[0][0]
                        if path.startswith('/'):
                            listing_url = f"https://www.trulia.com{path}"
                            if '/SINGLE-FAMILY_HOME_type/' not in listing_url:
                                listing_url = listing_url.rstrip('/') + '/SINGLE-FAMILY_HOME_type/'
                            logger.info(f"[LocationSearcher] Found listing URL from HTML: {listing_url}")
                            return listing_url
                
                # If no pattern found, return the redirect URL if it looks valid
                if 'trulia.com' in final_url and any(f'/{state}/' in final_url for state in ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC']):
                    if '/for_sale/' not in final_url:
                        match = re.search(r'/([A-Z]{2})/([^/]+)/?$', final_url)
                        if match:
                            state = match.group(1)
                            city = match.group(2)
                            return f"https://www.trulia.com/for_sale/{state}/{city}/SINGLE-FAMILY_HOME_type/"
                    return final_url
                    
            except Exception as e:
                logger.error(f"[LocationSearcher] GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Trulia: {e}")
        
        return None
    
    @classmethod
    def search_redfin(cls, location: str) -> Optional[str]:
        """
        Search Redfin for a location and return the actual listing URL.
        Redfin has a search box that processes location and redirects to listing page.
        """
        try:
            location_clean = location.strip()
            # Redfin search - use their search endpoint
            # Format can be: /city/{location}/for-sale-by-owner or search redirects
            search_url = f"https://www.redfin.com/stingray/api/gis?al=1&market=socal&num_homes=350&ord=redfin-recommended-asc&page_number=1&region_id=&region_type=2&sf=1,3,7&status=9&uipt=1,2,3,4,5,6,7,8&v=8&z=18&q={quote(location_clean)}"
            
            # Alternative: Try the simpler city search URL
            city_search_url = f"https://www.redfin.com/city/{quote(location_clean)}/for-sale-by-owner"
            
            logger.info(f"[LocationSearcher] Searching Redfin for: {location_clean}")
            logger.info(f"[LocationSearcher] Trying URL: {city_search_url}")
            
            try:
                response = requests.head(city_search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Redfin final URL: {final_url}")
                
                if 'redfin.com' in final_url and ('/for-sale-by-owner' in final_url or '/city/' in final_url or any(f'/{state}/' in final_url for state in URLDetector.US_STATES)):
                    if '/for-sale-by-owner' not in final_url:
                        # Check if it's a valid location page
                        if '/city/' in final_url or any(f'/{state}/' in final_url for state in URLDetector.US_STATES):
                            return f"{final_url.rstrip('/')}/for-sale-by-owner"
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Redfin HEAD request failed: {e}, trying GET")
            
            try:
                response = requests.get(city_search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'redfin.com' in final_url:
                    if '/for-sale-by-owner' not in final_url and ('/city/' in final_url or any(f'/{state}/' in final_url for state in URLDetector.US_STATES)):
                        return f"{final_url.rstrip('/')}/for-sale-by-owner"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] Redfin GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Redfin: {e}")
        
        return None
    
    @classmethod
    def search_apartments(cls, location: str) -> Optional[str]:
        """Search Apartments.com for a location and return the actual listing URL."""
        try:
            location_clean = location.strip().lower().replace(' ', '-').replace(',', '-')
            # Apartments.com format: /city-state/for-rent-by-owner/
            # Try to parse location to city-state format
            location_formatted = re.sub(r'[^a-z0-9-]', '', location_clean)
            search_url = f"https://www.apartments.com/{location_formatted}/for-rent-by-owner/"
            
            logger.info(f"[LocationSearcher] Searching Apartments.com for: {location_clean}")
            
            try:
                response = requests.head(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Apartments.com final URL: {final_url}")
                
                if 'apartments.com' in final_url:
                    if '/for-rent-by-owner/' not in final_url:
                        # Try to extract city-state from URL and append for-rent-by-owner
                        match = re.search(r'/([a-z0-9-]+(?:-[a-z]{2})?)/', final_url)
                        if match:
                            city_state = match.group(1)
                            return f"https://www.apartments.com/{city_state}/for-rent-by-owner/"
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Apartments.com HEAD request failed: {e}, trying GET")
            
            try:
                response = requests.get(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'apartments.com' in final_url:
                    if '/for-rent-by-owner/' not in final_url:
                        match = re.search(r'/([a-z0-9-]+(?:-[a-z]{2})?)/', final_url)
                        if match:
                            city_state = match.group(1)
                            return f"https://www.apartments.com/{city_state}/for-rent-by-owner/"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] Apartments.com GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Apartments.com: {e}")
        
        return None
    
    @classmethod
    def search_hotpads(cls, location: str) -> Optional[str]:
        """Search Hotpads for a location and return the actual listing URL."""
        try:
            location_clean = location.strip().lower().replace(' ', '-').replace(',', '-')
            location_formatted = re.sub(r'[^a-z0-9-]', '', location_clean)
            search_url = f"https://hotpads.com/{location_formatted}/apartments-for-rent"
            
            logger.info(f"[LocationSearcher] Searching Hotpads for: {location_clean}")
            
            try:
                response = requests.head(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Hotpads final URL: {final_url}")
                
                if 'hotpads.com' in final_url:
                    if '/apartments-for-rent' not in final_url:
                        match = re.search(r'/([a-z0-9-]+)/', final_url)
                        if match:
                            loc = match.group(1)
                            return f"https://hotpads.com/{loc}/apartments-for-rent"
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Hotpads HEAD request failed: {e}, trying GET")
            
            try:
                response = requests.get(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'hotpads.com' in final_url:
                    if '/apartments-for-rent' not in final_url:
                        match = re.search(r'/([a-z0-9-]+)/', final_url)
                        if match:
                            loc = match.group(1)
                            return f"https://hotpads.com/{loc}/apartments-for-rent"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] Hotpads GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Hotpads: {e}")
        
        return None
    
    @classmethod
    def search_zillow_fsbo(cls, location: str) -> Optional[str]:
        """
        Search Zillow FSBO for a location and return the actual listing URL.
        Zillow FSBO uses base URL: /homes/fsbo/ then searches for location
        The location can be added as path or query parameter after /fsbo/
        """
        try:
            location_clean = location.strip()
            # Zillow FSBO base URL format: /homes/fsbo/ or /homes/{location}/fsbo_rb/
            # Try both approaches
            search_url1 = f"https://www.zillow.com/homes/{quote(location_clean)}/fsbo_rb/"
            search_url2 = f"https://www.zillow.com/homes/fsbo/{quote(location_clean)}/"
            
            logger.info(f"[LocationSearcher] Searching Zillow FSBO for: {location_clean}")
            logger.info(f"[LocationSearcher] Trying URL 1: {search_url1}")
            
            # Try first format: /homes/{location}/fsbo_rb/
            try:
                response = requests.head(search_url1, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Zillow FSBO final URL (format 1): {final_url}")
                
                if 'zillow.com' in final_url and ('/homes/' in final_url and ('/fsbo' in final_url or 'fsbo=true' in final_url or 'fsbo' in final_url.lower())):
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Zillow FSBO format 1 HEAD failed: {e}, trying format 2")
            
            # Try second format: /homes/fsbo/{location}/
            try:
                response = requests.head(search_url2, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Zillow FSBO final URL (format 2): {final_url}")
                
                if 'zillow.com' in final_url and '/homes/' in final_url:
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Zillow FSBO format 2 HEAD failed: {e}, trying GET")
            
            # Fallback: Try GET requests
            try:
                response = requests.get(search_url1, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'zillow.com' in final_url and '/homes/' in final_url:
                    # Ensure fsbo is in the URL
                    if '/fsbo' not in final_url and 'fsbo=true' not in final_url:
                        # Add fsbo parameter
                        if '?' in final_url:
                            return f"{final_url}&fsbo=true"
                        else:
                            return f"{final_url.rstrip('/')}/fsbo_rb/"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] Zillow FSBO GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Zillow FSBO: {e}")
        
        return None
    
    @classmethod
    def search_zillow_frbo(cls, location: str) -> Optional[str]:
        """
        Search Zillow FRBO for a location and return the actual listing URL.
        Zillow FRBO uses base URL: /homes/for_rent/ with location in path or parameters
        """
        try:
            location_clean = location.strip()
            # Zillow FRBO search: /homes/{location}/for_rent/
            search_url = f"https://www.zillow.com/homes/{quote(location_clean)}/for_rent/"
            
            logger.info(f"[LocationSearcher] Searching Zillow FRBO for: {location_clean}")
            logger.info(f"[LocationSearcher] Trying URL: {search_url}")
            
            try:
                response = requests.head(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] Zillow FRBO final URL: {final_url}")
                
                if 'zillow.com' in final_url and ('/homes/' in final_url or '/for_rent' in final_url):
                    if '/for_rent' not in final_url and '/homes/' in final_url:
                        return f"{final_url.rstrip('/')}/for_rent/"
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] Zillow FRBO HEAD request failed: {e}, trying GET")
            
            try:
                response = requests.get(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'zillow.com' in final_url and '/homes/' in final_url:
                    if '/for_rent' not in final_url:
                        return f"{final_url.rstrip('/')}/for_rent/"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] Zillow FRBO GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Zillow FRBO: {e}")
        
        return None
    
    @classmethod
    def search_fsbo(cls, location: str) -> Optional[str]:
        """Search ForSaleByOwner.com for a location and return the actual listing URL."""
        try:
            location_clean = location.strip().lower().replace(' ', '-').replace(',', '-')
            location_formatted = re.sub(r'[^a-z0-9-]', '', location_clean)
            search_url = f"https://www.forsalebyowner.com/search/list/{location_formatted}"
            
            logger.info(f"[LocationSearcher] Searching FSBO for: {location_clean}")
            
            try:
                response = requests.head(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                logger.info(f"[LocationSearcher] FSBO final URL: {final_url}")
                
                if 'forsalebyowner.com' in final_url:
                    if '/search/list/' not in final_url and '/search/' in final_url:
                        match = re.search(r'/search/([^/]+)', final_url)
                        if match:
                            return f"https://www.forsalebyowner.com/search/list/{match.group(1)}"
                    return final_url
            except Exception as e:
                logger.warning(f"[LocationSearcher] FSBO HEAD request failed: {e}, trying GET")
            
            try:
                response = requests.get(search_url, headers=cls.HEADERS, allow_redirects=True, timeout=10)
                final_url = response.url
                
                if 'forsalebyowner.com' in final_url:
                    if '/search/list/' not in final_url and '/search/' in final_url:
                        match = re.search(r'/search/([^/]+)', final_url)
                        if match:
                            return f"https://www.forsalebyowner.com/search/list/{match.group(1)}"
                    return final_url
            except Exception as e:
                logger.error(f"[LocationSearcher] FSBO GET request failed: {e}")
                
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching FSBO: {e}")
        
        return None
    
    @classmethod
    def search_platform(cls, platform: str, location: str) -> Optional[str]:
        """
        Search a platform for a location and return the actual listing URL.
        
        Args:
            platform: Platform identifier (trulia, redfin, apartments.com, etc.)
            location: Location string (city name, city+state, zipcode, etc.)
            
        Returns:
            URL string if found, None otherwise
        """
        if not platform or not location:
            return None
        
        location = location.strip()
        if not location:
            return None
        
        platform_lower = platform.lower()
        
        # Map platform names to search methods
        platform_map = {
            'trulia': cls.search_trulia,
            'redfin': cls.search_redfin,
            'apartments.com': cls.search_apartments,
            'hotpads': cls.search_hotpads,
            'zillow_fsbo': cls.search_zillow_fsbo,
            'zillow_frbo': cls.search_zillow_frbo,
            'fsbo': cls.search_fsbo,
        }
        
        search_method = platform_map.get(platform_lower)
        if search_method:
            return search_method(location)
        
        logger.warning(f"[LocationSearcher] Unknown platform: {platform}")
        return None

