"""
Redfin platform search module.
Isolated from other platforms to prevent cascading failures.
"""

import re
import os
import json
import time
import logging
import requests
from typing import Optional
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

from .base import get_driver

logger = logging.getLogger(__name__)


def _load_redfin_id_cache() -> dict:
    """Load Redfin city ID cache from file."""
    cache_file = os.path.join(os.path.dirname(__file__), '..', 'redfin_city_ids_cache.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[Redfin] Failed to load Redfin ID cache: {e}")
    return {}


def _save_redfin_id_cache(cache: dict):
    """Save Redfin city ID cache to file."""
    cache_file = os.path.join(os.path.dirname(__file__), '..', 'redfin_city_ids_cache.json')
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.warning(f"[Redfin] Failed to save Redfin ID cache: {e}")


def _fetch_redfin_city_id(city: str, state_abbrev: str) -> Optional[str]:
    """
    Attempt to fetch Redfin city ID using multiple methods.
    This is a fallback when the city ID is not in our mapping.
    
    First checks persistent cache, then tries multiple API methods.
    Successfully fetched IDs are saved to cache for future use.
    
    Args:
        city: City name
        state_abbrev: State abbreviation (lowercase)
        
    Returns:
        City ID as string, or None if not found
    """
    # Check persistent cache first
    cache_key = f"{city.lower()},{state_abbrev.lower()}"
    cache = _load_redfin_id_cache()
    if cache_key in cache:
        cached_id = cache[cache_key]
        logger.info(f"[Redfin] Found Redfin city ID in cache: {cached_id} for {city}, {state_abbrev}")
        return cached_id
    
    # Helper function to save ID to cache and return it
    def save_and_return(city_id: str) -> str:
        cache[cache_key] = city_id
        _save_redfin_id_cache(cache)
        logger.info(f"[Redfin] Saved Redfin city ID to cache: {city_id} for {city}, {state_abbrev}")
        return city_id
    
    try:
        search_query = f"{city}, {state_abbrev.upper()}"
        city_slug = city.replace(' ', '-').lower()
        
        # Bing Search - Extract Redfin URLs directly
        # This avoids Redfin's bot detection by getting the URL from search results
        try:
            search_query = f'site:redfin.com "{city}, {state_abbrev.upper()}" "redfin.com/city/"'
            logger.info(f"[Redfin] 🔍 Trying Bing search: {search_query}")
            print(f"[Redfin] 🔍 Trying Bing search to extract Redfin URL...")
            
            # Use Zyte proxy if available to reduce bot detection
            use_proxy = os.getenv('ZYTE_API_KEY') is not None
            driver = get_driver(use_zyte_proxy=use_proxy)
            
            try:
                bing_url = f"https://www.bing.com/search?q={requests.utils.quote(search_query)}"
                logger.info(f"[Redfin] Navigating to Bing search: {bing_url}")
                print(f"[Redfin] Opening Bing search...")
                driver.get(bing_url)
                time.sleep(3)  # Wait for page to load
                
                # Check for CAPTCHA and try to solve it
                page_source = driver.page_source.lower()
                if 'captcha' in page_source or 'challenge' in page_source or 'verify' in page_source:
                    logger.info(f"[Redfin] Bing showed CAPTCHA, attempting to solve...")
                    print(f"[Redfin] Bing showed CAPTCHA, attempting to solve...")
                    
                    # Try to find and click CAPTCHA checkbox
                    captcha_selectors = [
                        'iframe[title*="reCAPTCHA" i]',
                        'iframe[src*="recaptcha" i]',
                        'div[class*="recaptcha" i]',
                        'div[id*="recaptcha" i]',
                        'iframe[title*="challenge" i]',
                        'div[class*="captcha" i]',
                        'div[id*="captcha" i]',
                        'button[id*="captcha" i]',
                        'input[type="checkbox"][id*="captcha" i]',
                    ]
                    
                    captcha_solved = False
                    for selector in captcha_selectors:
                        try:
                            # Try to find CAPTCHA iframe first
                            iframes = driver.find_elements(By.CSS_SELECTOR, selector)
                            for iframe in iframes:
                                try:
                                    # Switch to iframe
                                    driver.switch_to.frame(iframe)
                                    # Look for checkbox inside iframe
                                    checkbox = driver.find_element(By.CSS_SELECTOR, 'span[role="checkbox"], .recaptcha-checkbox, #recaptcha-anchor')
                                    if checkbox:
                                        logger.info(f"[Redfin] Found CAPTCHA checkbox, clicking...")
                                        checkbox.click()
                                        time.sleep(2)
                                        captcha_solved = True
                                        driver.switch_to.default_content()
                                        break
                                except:
                                    driver.switch_to.default_content()
                                    continue
                            
                            if captcha_solved:
                                break
                            
                            # Try direct CAPTCHA elements (not in iframe)
                            captcha_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in captcha_elements:
                                if 'iframe' not in element.tag_name.lower():
                                    try:
                                        element.click()
                                        time.sleep(2)
                                        captcha_solved = True
                                        logger.info(f"[Redfin] Clicked CAPTCHA element")
                                        break
                                    except:
                                        continue
                            
                            if captcha_solved:
                                break
                        except:
                            continue
                    
                    if captcha_solved:
                        logger.info(f"[Redfin] CAPTCHA clicked, waiting for verification...")
                        time.sleep(3)  # Wait for CAPTCHA to verify
                        
                        # Check if CAPTCHA is still present
                        page_source = driver.page_source.lower()
                        if 'captcha' in page_source or 'challenge' in page_source:
                            logger.warning(f"[Redfin] CAPTCHA still present after clicking")
                            print(f"[Redfin] ⚠️ CAPTCHA still present after clicking")
                        else:
                            logger.info(f"[Redfin] CAPTCHA appears to be solved!")
                            print(f"[Redfin] ✓ CAPTCHA solved!")
                
                # Human-like behavior: scroll a bit
                driver.execute_script("window.scrollTo(0, 300);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                # Parse the search results
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                logger.info(f"[Redfin] Parsing Bing search results HTML...")
                
                # Find all links in search results
                links = soup.find_all('a', href=True)
                logger.info(f"[Redfin] Found {len(links)} links in Bing results")
                
                redfin_links_found = 0
                for link in links:
                    href = link.get('href', '')
                    
                    # Bing links are usually direct, skip relative URLs
                    if href.startswith('/'):
                        continue
                    
                    # Extract Redfin city URLs
                    if 'redfin.com/city/' in href:
                        redfin_links_found += 1
                        # Extract city ID from URL pattern: /city/{ID}/STATE/City-Name
                        match = re.search(r'/city/(\d+)/', href)
                        if match:
                            found_id = match.group(1)
                            logger.info(f"[Redfin] Found potential city ID {found_id} in URL: {href}")
                            # Verify it's for our city/state (more flexible matching)
                            href_lower = href.lower()
                            city_match = city_slug.replace('-', ' ').lower() in href_lower or city.lower() in href_lower
                            state_match = state_abbrev.upper() in href.upper()
                            if city_match and state_match:
                                logger.info(f"[Redfin] ✓ Found Redfin city ID via Bing search: {found_id}")
                                print(f"[Redfin] ✓ Found Redfin city ID via Bing search: {found_id}")
                                driver.quit()
                                return save_and_return(found_id)
                            else:
                                logger.debug(f"[Redfin] City ID {found_id} doesn't match city/state criteria (city_match={city_match}, state_match={state_match})")
                
                logger.info(f"[Redfin] Found {redfin_links_found} Redfin links in Bing results")
                
                # Also try extracting from page source text
                page_text = driver.page_source
                matches = re.findall(r'redfin\.com/city/(\d+)/[^"\'<>\s]+', page_text)
                for found_id in matches:
                    # Check if this ID appears in a URL that matches our city/state
                    url_pattern = f'redfin.com/city/{found_id}/[^"\'<>\s]+'
                    url_matches = re.findall(url_pattern, page_text)
                    for url_match in url_matches:
                        url_lower = url_match.lower()
                        city_match = city_slug.replace('-', ' ').lower() in url_lower or city.lower() in url_lower
                        state_match = state_abbrev.upper() in url_match.upper()
                        if city_match and state_match:
                            logger.info(f"[Redfin] ✓ Found Redfin city ID via Bing text extraction: {found_id}")
                            print(f"[Redfin] ✓ Found Redfin city ID via Bing text extraction: {found_id}")
                            driver.quit()
                            return save_and_return(found_id)
                
                logger.warning(f"[Redfin] Bing search completed but no matching city ID found")
                print(f"[Redfin] ⚠️ Bing search completed but no matching city ID found")
                driver.quit()
                
            except Exception as e:
                logger.warning(f"[Redfin] Bing search failed: {e}")
                print(f"[Redfin] ⚠️ Bing search failed: {e}")
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                raise
                
        except Exception as e:
            logger.warning(f"[Redfin] Bing search crawler failed: {e}")
            print(f"[Redfin] ⚠️ Bing search crawler failed: {e}")
            import traceback
            logger.debug(f"[Redfin] Bing search crawler traceback: {traceback.format_exc()}")
        
        # No fallback methods - if Bing fails, return None
        logger.warning(f"[Redfin] Bing search failed, no fallback methods available")
        return None
    except Exception as e:
        logger.error(f"[Redfin] Error fetching Redfin city ID: {e}")
        return None


def construct_redfin_url(location: str) -> Optional[str]:
    """
    Construct Redfin URL directly from location name without browser automation.
    
    Pattern: https://www.redfin.com/city/{CITY_ID}/{STATE}/{CITY-NAME}
    Examples:
        - "Los Angeles, CA" -> "https://www.redfin.com/city/11203/CA/Los-Angeles"
        - "Minneapolis, MN" -> "https://www.redfin.com/city/10943/MN/Minneapolis"
        - "New York, NY" -> "https://www.redfin.com/city/30749/NY/New-York"
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY", "Minneapolis")
        
    Returns:
        Constructed Redfin URL or None if location cannot be parsed or city ID not found
    """
    location_clean = location.strip()
    logger.info(f"[Redfin] Constructing Redfin URL for: {location_clean}")
    
    # State abbreviations mapping (full name -> abbrev)
    state_mapping = {
        'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
        'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
        'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi', 'idaho': 'id',
        'illinois': 'il', 'indiana': 'in', 'iowa': 'ia', 'kansas': 'ks',
        'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
        'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn', 'mississippi': 'ms',
        'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne', 'nevada': 'nv',
        'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm', 'new york': 'ny',
        'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh', 'oklahoma': 'ok',
        'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri', 'south carolina': 'sc',
        'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx', 'utah': 'ut',
        'vermont': 'vt', 'virginia': 'va', 'washington': 'wa', 'west virginia': 'wv',
        'wisconsin': 'wi', 'wyoming': 'wy', 'district of columbia': 'dc'
    }
    
    # City-to-state mapping for major cities (when only city name is provided)
    city_to_state = {
        'minneapolis': 'mn', 'new york': 'ny', 'los angeles': 'ca', 'chicago': 'il',
        'houston': 'tx', 'phoenix': 'az', 'philadelphia': 'pa', 'san antonio': 'tx',
        'san diego': 'ca', 'dallas': 'tx', 'san jose': 'ca', 'austin': 'tx',
        'jacksonville': 'fl', 'fort worth': 'tx', 'columbus': 'oh', 'charlotte': 'nc',
        'san francisco': 'ca', 'indianapolis': 'in', 'seattle': 'wa', 'denver': 'co',
        'washington': 'dc', 'boston': 'ma', 'el paso': 'tx', 'detroit': 'mi',
        'nashville': 'tn', 'portland': 'or', 'oklahoma city': 'ok', 'las vegas': 'nv',
        'memphis': 'tn', 'louisville': 'ky', 'baltimore': 'md', 'milwaukee': 'wi',
        'albuquerque': 'nm', 'tucson': 'az', 'fresno': 'ca', 'sacramento': 'ca',
        'kansas city': 'mo', 'mesa': 'az', 'atlanta': 'ga', 'omaha': 'ne',
        'colorado springs': 'co', 'raleigh': 'nc', 'virginia beach': 'va', 'miami': 'fl',
        'oakland': 'ca', 'tulsa': 'ok', 'cleveland': 'oh', 'wichita': 'ks',
        'arlington': 'tx', 'new orleans': 'la', 'tampa': 'fl', 'honolulu': 'hi',
        'st. louis': 'mo', 'st louis': 'mo', 'cincinnati': 'oh', 'pittsburgh': 'pa',
        'buffalo': 'ny', 'st. paul': 'mn', 'st paul': 'mn', 'corpus christi': 'tx',
        'aurora': 'co', 'newark': 'nj', 'plano': 'tx', 'henderson': 'nv',
        'lincoln': 'ne', 'greensboro': 'nc', 'durham': 'nc', 'jersey city': 'nj',
        'chula vista': 'ca', 'scottsdale': 'az', 'norfolk': 'va', 'madison': 'wi',
        'orlando': 'fl', 'chandler': 'az', 'laredo': 'tx', 'lubbock': 'tx',
        'garland': 'tx', 'hialeah': 'fl', 'reno': 'nv', 'chesapeake': 'va',
        'gilbert': 'az', 'baton rouge': 'la', 'irving': 'tx', 'glendale': 'az',
        'richmond': 'va', 'boise': 'id', 'san bernardino': 'ca', 'spokane': 'wa',
        'birmingham': 'al', 'modesto': 'ca', 'rochester': 'ny', 'des moines': 'ia',
        'fayetteville': 'nc', 'tacoma': 'wa', 'fontana': 'ca', 'oxnard': 'ca',
        'moreno valley': 'ca', 'shreveport': 'la', 'aurora': 'il', 'yonkers': 'ny',
        'akron': 'oh', 'huntington beach': 'ca', 'little rock': 'ar', 'amarillo': 'tx',
        'grand rapids': 'mi', 'mobile': 'al', 'salt lake city': 'ut', 'tallahassee': 'fl',
        'grand prairie': 'tx', 'overland park': 'ks', 'knoxville': 'tn',
        'winston-salem': 'nc', 'winston salem': 'nc', 'sioux falls': 'sd',
        'peoria': 'az', 'providence': 'ri', 'gainesville': 'fl', 'frisco': 'tx',
        'tempe': 'az', 'mcallen': 'tx', 'fort lauderdale': 'fl', 'brownsville': 'tx',
        'ontario': 'ca', 'santa ana': 'ca', 'elgin': 'il', 'vancouver': 'wa',
        'nampa': 'id', 'mckinney': 'tx', 'fremont': 'ca', 'stockton': 'ca',
        'richmond': 'ca', 'irvine': 'ca', 'troy': 'ny', 'alabama': 'ny'
    }
    
    # City-to-Redfin-ID mapping (city name -> city ID)
    # Format: (city_name_lower, state_abbrev) -> city_id
    city_to_redfin_id = {
        ('los angeles', 'ca'): '11203',
        ('minneapolis', 'mn'): '10943',
        ('new york', 'ny'): '30749',
        ('troy', 'ny'): '19127',
        ('alabama', 'ny'): '29841',
        # Additional common cities from web research
        ('chicago', 'il'): '29470',
        ('houston', 'tx'): '30794',
        ('phoenix', 'az'): '9258',
        ('philadelphia', 'pa'): '13271',
        ('san antonio', 'tx'): '17712',
        ('san diego', 'ca'): '17766',
        ('dallas', 'tx'): '25234',
        ('austin', 'tx'): '25230',
        ('san francisco', 'ca'): '17764',  # San Francisco, CA
        ('alfred', 'ny'): '29847',  # Alfred, NY
        # Note: Washington DC city ID not yet in mapping - will use API fallback
    }
    
    # Try to extract city and state from location string
    city = None
    state_abbrev = None
    
    # Pattern 1: "City, State" or "City, ST" (comma separated)
    match = re.match(r'^(.+?),\s*([A-Z]{2}|[A-Za-z\s]+)$', location_clean)
    if match:
        city = match.group(1).strip()
        state_part = match.group(2).strip()
        
        # Check if state_part is already an abbreviation (2 letters)
        if len(state_part) == 2 and state_part.upper() in [s.upper() for s in state_mapping.values()]:
            state_abbrev = state_part.lower()
        else:
            # Try to find state abbreviation from full name
            state_lower = state_part.lower()
            if state_lower in state_mapping:
                state_abbrev = state_mapping[state_lower]
    
    # Pattern 2: "City ST" (space separated, 2-letter state at end)
    if not city or not state_abbrev:
        match = re.match(r'^(.+?)\s+([A-Z]{2})$', location_clean)
        if match:
            city = match.group(1).strip()
            state_abbrev = match.group(2).strip().lower()
    
    # Pattern 3: Try to find state abbreviation anywhere in the string
    if not state_abbrev:
        state_match = re.search(r'\b([A-Z]{2})\b', location_clean)
        if state_match:
            potential_state = state_match.group(1).lower()
            if potential_state in state_mapping.values():
                state_abbrev = potential_state
                city = location_clean[:state_match.start()].strip()
    
    # Before checking for full state names, check city-to-state mapping first
    # This handles cases like "New York" which is both a city and a state name
    if not state_abbrev:
        location_lower = location_clean.lower().strip()
        # Try exact match first
        if location_lower in city_to_state:
            state_abbrev = city_to_state[location_lower]
            city = location_clean  # Use the full location as city
        else:
            # Try to find a city name that matches (handles multi-word cities)
            for city_name, state_code in city_to_state.items():
                if location_lower == city_name or location_lower.startswith(city_name + ' ') or location_lower.endswith(' ' + city_name):
                    state_abbrev = state_code
                    city = location_clean  # Use the full location as city
                    break
    
    # Pattern 4: Try to find full state name
    if not state_abbrev:
        for state_name, abbrev in state_mapping.items():
            if state_name in location_clean.lower():
                state_abbrev = abbrev
                state_index = location_clean.lower().find(state_name)
                city = location_clean[:state_index].strip()
                break
    
    # If no city found, use the whole location as city (minus state)
    if not city:
        city = location_clean
        for state_name, abbrev in state_mapping.items():
            city = re.sub(rf'\b{state_name}\b', '', city, flags=re.IGNORECASE).strip()
        city = re.sub(rf'\b{state_abbrev}\b', '', city, flags=re.IGNORECASE).strip() if state_abbrev else city
        city = re.sub(r'[,\s]+', ' ', city).strip()
    
    if not city:
        logger.warning(f"[Redfin] Could not extract city from location: {location_clean}")
        print(f"[Redfin] ⚠️ Could not extract city from location")
        return None
    
    if not state_abbrev:
        logger.warning(f"[Redfin] Could not extract state from location: {location_clean}")
        print(f"[Redfin] ⚠️ Could not extract state from location")
        return None
    
    # Look up Redfin city ID
    city_lower = city.lower().strip()
    city_id = city_to_redfin_id.get((city_lower, state_abbrev))
    
    # If not in mapping, try to fetch from Redfin API
    if not city_id:
        logger.info(f"[Redfin] City ID not in mapping for ({city_lower}, {state_abbrev}), attempting to fetch from Redfin API...")
        print(f"[Redfin] City ID not in mapping, attempting to fetch from Redfin API...")
        city_id = _fetch_redfin_city_id(city, state_abbrev)
        
        if city_id:
            # Cache it for future use (optional - you could save to a file/db)
            logger.info(f"[Redfin] Successfully fetched city ID: {city_id}")
            print(f"[Redfin] ✓ Successfully fetched city ID from API: {city_id}")
        else:
            logger.warning(f"[Redfin] Redfin city ID not found for: {city}, {state_abbrev.upper()}")
            print(f"[Redfin] ⚠️ Redfin city ID not found for: {city}, {state_abbrev.upper()}")
            # Log what we tried for debugging
            logger.debug(f"[Redfin] Tried to fetch city ID for: city='{city}', state='{state_abbrev}', city_lower='{city_lower}'")
            return None
    
    # Convert city to URL format: title case, replace spaces with hyphens
    city_slug = city.strip()
    city_slug = re.sub(r'\s+', '-', city_slug)  # Replace spaces with hyphens
    city_slug = re.sub(r'-+', '-', city_slug)  # Replace multiple hyphens with single
    city_slug = city_slug.strip('-')  # Remove leading/trailing hyphens
    
    # Construct URL
    url = f"https://www.redfin.com/city/{city_id}/{state_abbrev.upper()}/{city_slug}"
    logger.info(f"[Redfin] ✓ Constructed Redfin URL: {url}")
    print(f"[Redfin] ✓ Constructed Redfin URL directly: {url}")
    return url


def search_redfin(location: str) -> Optional[str]:
    """
    Search Redfin for a location using direct URL construction.
    
    Constructs the Redfin URL directly from location.
    No browser automation needed - much faster and more reliable!
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY", "Minneapolis")
        
    Returns:
        Constructed Redfin URL or None if location cannot be parsed or city ID not found
    """
    location_clean = location.strip()
    logger.info(f"[Redfin] Searching Redfin for: {location_clean}")
    
    # Construct URL directly (no browser needed!)
    url = construct_redfin_url(location_clean)
    if url:
        print(f"[Redfin] ✓ Using direct URL construction (no browser needed)")
        return url
    
    # If URL construction failed, return None
    logger.warning(f"[Redfin] Could not construct Redfin URL for: {location_clean}")
    print(f"[Redfin] ⚠️ Could not construct URL - location format may be invalid or city ID not in mapping")
    return None

