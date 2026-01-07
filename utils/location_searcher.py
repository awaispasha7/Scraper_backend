"""
Location Search Utilities
Searches platforms to get the actual listing URL from a location name
Uses Selenium to actually interact with search boxes like a real user
"""

import re
import time
from typing import Optional
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

class LocationSearcher:
    """Search platforms for location and return the actual listing URL using browser automation"""
    
    @classmethod
    def _get_driver(cls):
        """Create and return a Chrome WebDriver instance using same setup as FSBO scraper"""
        import os
        import sys
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Check for Browserless.io token
        browserless_token = os.getenv("BROWSERLESS_TOKEN")
        
        if browserless_token:
            logger.info("[LocationSearcher] Connecting to Browserless.io...")
            browserless_url = f"https://chrome.browserless.io/webdriver?token={browserless_token}"
            driver = webdriver.Remote(
                command_executor=browserless_url,
                options=chrome_options
            )
        else:
            service = Service()
            if sys.platform.startswith('linux'):
                chrome_binary = '/usr/bin/chromium'
                chrome_driver = '/usr/bin/chromedriver'
                
                if os.path.exists(chrome_binary) and os.path.exists(chrome_driver):
                    chrome_options.binary_location = chrome_binary
                    service = Service(executable_path=chrome_driver)
                    logger.info(f"[LocationSearcher] Using system Chromium ({chrome_binary}) and Driver ({chrome_driver})")
                elif os.path.exists(chrome_binary):
                    chrome_options.binary_location = chrome_binary
                    logger.info(f"[LocationSearcher] Using system Chromium ({chrome_binary})")
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.maximize_window()
        return driver
    
    @classmethod
    def search_trulia(cls, location: str) -> Optional[str]:
        """
        Search Trulia for a location using their search box.
        After search, URL format examples:
        - https://www.trulia.com/MN/Minneapolis/
        - https://www.trulia.com/DC/Washington/
        - https://www.trulia.com/NY/New_York/
        
        Note: Trulia search box may show random text based on last searches,
        and placeholder is only visible when clicked. We use multiple strategies
        to find the search box reliably.
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.trulia.com")
            time.sleep(4)  # Wait for page to fully load
            
            wait = WebDriverWait(driver, 15)
            
            # Trulia search box strategies (in order of reliability):
            # 1. Look for input by structural position (usually the main hero search box)
            # 2. Look for input by id/class patterns
            # 3. Look for input by aria-label
            # 4. Click on visible inputs to reveal placeholder
            # 5. Fallback to any visible text input in the hero/search area
            
            search_box = None
            
            # Strategy 1: Look for input by specific selectors (most reliable)
            search_selectors = [
                # Common Trulia search box identifiers
                "input[type='text'][aria-label*='search']",
                "input[type='text'][aria-label*='Search']",
                "input[type='text'][id*='search']",
                "input[type='text'][name*='search']",
                "input[type='text'][class*='Search']",
                "input[type='text'][class*='search']",
                # Hero area search box (usually has specific classes)
                "div[class*='Hero'] input[type='text']",
                "div[class*='hero'] input[type='text']",
                "div[class*='SearchBox'] input[type='text']",
                "div[class*='search'] input[type='text']",
                # Form-based selectors
                "form input[type='text']",
            ]
            
            for selector in search_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Verify it's likely a location search (not price/beds/baths)
                            aria_label = (elem.get_attribute('aria-label') or '').lower()
                            placeholder = (elem.get_attribute('placeholder') or '').lower()
                            name_attr = (elem.get_attribute('name') or '').lower()
                            
                            # Skip if it's clearly not a location search
                            if any(skip_term in aria_label or skip_term in placeholder or skip_term in name_attr 
                                   for skip_term in ['price', 'bed', 'bath', 'min', 'max', 'filter']):
                                continue
                            
                            search_box = elem
                            logger.info(f"[LocationSearcher] Found Trulia search box using selector: {selector}")
                            break
                    if search_box:
                        break
                except Exception as e:
                    logger.debug(f"[LocationSearcher] Selector {selector} failed: {e}")
                    continue
            
            # Strategy 2: Click on visible inputs to reveal placeholder
            if not search_box:
                logger.info(f"[LocationSearcher] Trying to find search box by clicking visible inputs...")
                try:
                    all_text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                    for inp in all_text_inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            try:
                                # Click to activate and check placeholder
                                inp.click()
                                time.sleep(0.5)
                                placeholder = (inp.get_attribute('placeholder') or '').lower()
                                
                                # Check if placeholder contains location-related keywords
                                if any(keyword in placeholder for keyword in ['search for city', 'city, neighborhood', 'neighborhood', 'zip', 'county', 'location']):
                                    search_box = inp
                                    logger.info(f"[LocationSearcher] Found Trulia search box by clicking and checking placeholder: {placeholder[:60]}...")
                                    break
                            except:
                                continue
                except Exception as e:
                    logger.debug(f"[LocationSearcher] Error in click-to-reveal strategy: {e}")
            
            # Strategy 3: Find the largest/primary text input (usually the hero search)
            if not search_box:
                logger.info(f"[LocationSearcher] Trying to find largest visible text input...")
                try:
                    all_text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                    visible_inputs = [inp for inp in all_text_inputs if inp.is_displayed() and inp.is_enabled()]
                    
                    if visible_inputs:
                        # Sort by size (width * height) - hero search is usually largest
                        visible_inputs.sort(key=lambda x: (x.size['width'] * x.size['height']), reverse=True)
                        # Take the largest one that's not clearly a filter
                        for inp in visible_inputs[:3]:  # Check top 3 largest
                            aria_label = (inp.get_attribute('aria-label') or '').lower()
                            name_attr = (inp.get_attribute('name') or '').lower()
                            
                            # Skip filter inputs
                            if not any(skip_term in aria_label or skip_term in name_attr 
                                      for skip_term in ['price', 'bed', 'bath', 'min', 'max', 'filter']):
                                search_box = inp
                                logger.info(f"[LocationSearcher] Found Trulia search box by size (largest visible input)")
                                break
                except Exception as e:
                    logger.debug(f"[LocationSearcher] Error in size-based strategy: {e}")
            
            if not search_box:
                raise TimeoutException("Search box not found on Trulia after trying all strategies")
            
            # Click on the search box to ensure it's focused and placeholder is visible
            try:
                search_box.click()
                time.sleep(0.5)
            except:
                pass  # Continue even if click fails
            
            # Clear any existing text and enter location
            search_box.clear()
            time.sleep(0.5)
            search_box.send_keys(location_clean)
            logger.info(f"[LocationSearcher] Entered '{location_clean}' into Trulia search box")
            time.sleep(2.5)  # Wait for autocomplete suggestions to appear
            
            # Wait for and click the first autocomplete suggestion
            try:
                # Wait for suggestions to appear - try multiple selectors
                suggestion_selectors = [
                    "ul[role='listbox'] li",
                    "div[role='listbox'] div[role='option']",
                    "ul[class*='autocomplete'] li",
                    "div[class*='autocomplete'] div",
                    "div[class*='suggestion']",
                    "li[class*='suggestion']",
                    "div[class*='SearchAutocomplete'] div",
                    "div[class*='search'] div[class*='option']"
                ]
                
                suggestions = []
                for selector in suggestion_selectors:
                    try:
                        suggestions = WebDriverWait(driver, 3).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                        if suggestions and len(suggestions) > 0:
                            logger.info(f"[LocationSearcher] Found {len(suggestions)} autocomplete suggestions using selector: {selector}")
                            break
                    except TimeoutException:
                        continue
                
                if suggestions and len(suggestions) > 0:
                    # Filter to only visible suggestions
                    visible_suggestions = [s for s in suggestions if s.is_displayed()]
                    if visible_suggestions:
                        logger.info(f"[LocationSearcher] Clicking first visible suggestion: {visible_suggestions[0].text[:50]}...")
                        visible_suggestions[0].click()
                        time.sleep(3)  # Wait for redirect after clicking
                    else:
                        logger.info(f"[LocationSearcher] No visible suggestions, pressing Enter key")
                        search_box.send_keys(Keys.RETURN)
                        time.sleep(3)
                else:
                    # No suggestions, try Enter key
                    logger.info(f"[LocationSearcher] No suggestions found, pressing Enter key")
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except TimeoutException:
                # Suggestions didn't appear, try Enter key
                logger.info(f"[LocationSearcher] Suggestions timeout, pressing Enter key")
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            except Exception as e:
                logger.warning(f"[LocationSearcher] Error with suggestions: {e}, using Enter key")
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            # Get the final URL after redirect
            time.sleep(2)  # Extra wait for redirect
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Trulia final URL: {current_url}")
            
            # Simply return whatever URL we ended up on
            if 'trulia.com' in current_url:
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Trulia search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Trulia: {e}")
            import traceback
            logger.error(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_apartments(cls, location: str) -> Optional[str]:
        """
        Search Apartments.com for a location using their search box.
        Enters the location, clicks search, and returns the resulting URL.
        Note: Apartments.com URLs are always in format: https://www.apartments.com/hub/{location}/
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Apartments.com for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.apartments.com")
            time.sleep(2)  # Wait for page to load
            
            # Wait for search box - Apartments.com uses placeholder like "New York, NY"
            wait = WebDriverWait(driver, 15)
            
            # First try to find by placeholder text - Apartments.com uses "Location, School, or Point of Interest"
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        aria_label = (inp.get_attribute('aria-label') or '').lower()
                        # Apartments.com placeholder is: "Location, School, or Point of Interest"
                        if any(keyword in placeholder for keyword in ['location, school', 'location, school, or point', 'location school', 'point of interest']):
                            search_box = inp
                            logger.info(f"[LocationSearcher] Found Apartments.com search box by placeholder: {placeholder}")
                            break
                        # Also check for location in aria-label
                        if 'location' in aria_label and 'school' in aria_label:
                            search_box = inp
                            logger.info(f"[LocationSearcher] Found Apartments.com search box by aria-label: {aria_label}")
                            break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "input[aria-label*='Location']",
                    "input[placeholder*='Location']",
                    "input[placeholder*='New York']",  # City name pattern
                    "input[type='text'][name*='search']",
                    "input[id*='search']",
                    "input[class*='search']",
                    "input[aria-label*='search']"
                ]
                
                for selector in search_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                search_box = elem
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                raise TimeoutException("Search box not found on Apartments.com")
            
            # Clear the search box
            search_box.clear()
            time.sleep(0.5)
            
            # Enter location text
            search_box.send_keys(location_clean)
            logger.info(f"[LocationSearcher] Entered '{location_clean}' into Apartments.com search box")
            time.sleep(2)  # Wait for autocomplete suggestions to appear
            
            # Try to click on first autocomplete suggestion if available
            try:
                # Wait for suggestions to appear
                suggestions = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul[class*='autocomplete'] li, ul[class*='suggestion'] li, div[class*='suggestion'], li[class*='suggestion'], div[role='option'], ul[role='listbox'] li"))
                )
                if suggestions and len(suggestions) > 0:
                    logger.info(f"[LocationSearcher] Found {len(suggestions)} autocomplete suggestions, clicking first one")
                    suggestions[0].click()
                    time.sleep(3)  # Wait for redirect after clicking suggestion
                else:
                    # No suggestions, try clicking search button or pressing Enter
                    try:
                        search_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Search apartments'], button[aria-label*='search'], button[type='submit'], button[class*='search']")
                        logger.info(f"[LocationSearcher] Clicking search button")
                        search_button.click()
                        time.sleep(3)
                    except:
                        # Fallback to Enter key
                        logger.info(f"[LocationSearcher] Pressing Enter key")
                        search_box.send_keys(Keys.RETURN)
                        time.sleep(3)
            except TimeoutException:
                # No suggestions appeared, try pressing Enter or clicking search button
                logger.info(f"[LocationSearcher] No autocomplete suggestions, trying Enter key or search button")
                try:
                    search_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Search apartments'], button[aria-label*='search'], button[type='submit'], button[class*='search']")
                    search_button.click()
                    time.sleep(3)
                except:
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except Exception as e:
                # Fallback to Enter key
                logger.warning(f"[LocationSearcher] Error with suggestions/button: {e}, using Enter key")
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            # Wait a bit more for any redirects or page updates
            time.sleep(3)
            
            # Get the current URL after search - use whatever URL the website redirected us to
            # Examples: apartments.com/missouri-city-tx/ or apartments.com/hub/new-york-ny/
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Apartments.com final URL after search: {current_url}")
            
            # Simply return whatever URL we ended up on
            # The website's natural redirect will give us the correct URL format
            if 'apartments.com' in current_url:
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Apartments.com search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Apartments.com: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_redfin(cls, location: str) -> Optional[str]:
        """
        Search Redfin for a location using their search box.
        Enters the location, clicks search, and returns the resulting URL.
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Redfin for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.redfin.com")
            time.sleep(2)  # Wait for page to load
            
            # Wait for search box - Redfin uses placeholder "City, Address, School, Agent, ZIP"
            wait = WebDriverWait(driver, 15)
            
            # First try to find by placeholder text
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        # Redfin placeholder: "City, Address, School, Agent, ZIP"
                        if any(keyword in placeholder for keyword in ['city', 'address', 'school', 'agent', 'zip']):
                            search_box = inp
                            logger.info(f"[LocationSearcher] Found Redfin search box by placeholder: {placeholder}")
                            break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "input[placeholder*='City, Address']",
                    "input[placeholder*='city']",
                    "input[placeholder*='address']",
                    "input[id*='search']",
                    "input[name*='search']",
                    "input[aria-label*='search']",
                    "input[class*='search']"
                ]
                
                for selector in search_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                search_box = elem
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                raise TimeoutException("Search box not found on Redfin")
            
            # Clear and enter location
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)  # Wait for autocomplete
            
            # Try to click first suggestion or submit button
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "div[class*='suggestion'], li[class*='suggestion'], ul[class*='autocomplete'] li, div[role='option']")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button[aria-label*='search'], button[class*='search']")
                        submit_btn.click()
                    except:
                        search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            # Get current URL
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Redfin final URL: {current_url}")
            
            if 'redfin.com' in current_url:
                # Append for-sale-by-owner if needed
                if '/for-sale-by-owner' not in current_url:
                    if current_url.endswith('/'):
                        listing_url = f"{current_url}for-sale-by-owner"
                    else:
                        listing_url = f"{current_url}/for-sale-by-owner"
                    logger.info(f"[LocationSearcher] Built Redfin listing URL: {listing_url}")
                    return listing_url
                
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Redfin search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Redfin: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_hotpads(cls, location: str) -> Optional[str]:
        """Search Hotpads for a location using their search box."""
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Hotpads for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://hotpads.com")
            time.sleep(3)  # Wait for page to load
            
            wait = WebDriverWait(driver, 15)
            # Hotpads search box has placeholder like "Philadelphia, PA"
            # First try to find by placeholder text pattern
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        # Hotpads placeholder is typically a city, state format like "philadelphia, pa"
                        if ',' in placeholder and any(keyword in placeholder for keyword in ['pa', 'ny', 'ca', 'tx', 'il', 'fl']):
                            # Make sure it's not a filter (price, beds)
                            if 'price' not in placeholder and 'bed' not in placeholder:
                                search_box = inp
                                logger.info(f"[LocationSearcher] Found Hotpads search box by placeholder: {placeholder}")
                                break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "div[role='combobox'] input[type='text']",  # Input inside combobox (most specific)
                    "input[placeholder*='Philadelphia']",  # Pattern matching placeholder
                    "input[placeholder*='PA']",  # State abbreviation in placeholder
                    "input[aria-label*='Search listings']",  # ARIA label
                    "input[type='text']"  # Generic text input (will filter below)
                ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Filter out price and beds dropdowns
                            placeholder = (elem.get_attribute('placeholder') or '').lower()
                            aria_label = (elem.get_attribute('aria-label') or '').lower()
                            input_type = elem.get_attribute('type') or ''
                            
                            # Skip if it's clearly a filter (price, beds, etc.)
                            if any(word in placeholder or word in aria_label for word in ['price', 'bed', 'bath', 'any price', 'all bed']):
                                continue
                            
                            # If it's a text input and not a filter, it's likely the search box
                            if input_type == 'text' or selector == "div[role='combobox'] input[type='text']":
                                search_box = elem
                                logger.info(f"[LocationSearcher] Found Hotpads search box with selector: {selector}")
                                break
                    if search_box:
                        break
                except Exception as e:
                    logger.debug(f"[LocationSearcher] Selector {selector} failed: {e}")
                    continue
            
            # If still not found, try finding the first visible text input that's not a filter
            if not search_box:
                try:
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                    for inp in all_inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            placeholder = (inp.get_attribute('placeholder') or '').lower()
                            if 'price' not in placeholder and 'bed' not in placeholder and 'bath' not in placeholder:
                                search_box = inp
                                logger.info(f"[LocationSearcher] Found Hotpads search box as first non-filter input")
                                break
                except Exception as e:
                    logger.debug(f"[LocationSearcher] Fallback input search failed: {e}")
            
            if not search_box:
                raise TimeoutException("Search box not found on Hotpads")
            
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)  # Wait for autocomplete
            
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "div[class*='suggestion'], li[class*='suggestion'], ul[class*='autocomplete'] li, div[role='option'], ul[role='listbox'] li")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    # Click the Search button
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[name='Search'], button[aria-label*='Search'], button:contains('Search')")
                        submit_btn.click()
                    except:
                        # Try by text content
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.text.strip().lower() == 'search':
                                btn.click()
                                break
                        else:
                            search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                # Fallback to Enter key
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Hotpads final URL: {current_url}")
            
            if 'hotpads.com' in current_url:
                if '/apartments-for-rent' not in current_url:
                    if current_url.endswith('/'):
                        listing_url = f"{current_url}apartments-for-rent"
                    else:
                        listing_url = f"{current_url}/apartments-for-rent"
                    logger.info(f"[LocationSearcher] Built Hotpads listing URL: {listing_url}")
                    return listing_url
                
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Hotpads search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Hotpads: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_zillow_fsbo(cls, location: str) -> Optional[str]:
        """Search Zillow FSBO for a location using their search box."""
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Zillow FSBO for: {location_clean}")
            
            driver = cls._get_driver()
            # Go to FSBO page first
            driver.get("https://www.zillow.com/homes/fsbo/")
            time.sleep(3)  # Wait for page to load
            
            wait = WebDriverWait(driver, 15)
            # Zillow FSBO uses placeholder "Address, neighborhood, city, ZIP"
            # First try to find by placeholder text
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        # Zillow placeholder: "Address, neighborhood, city, ZIP"
                        if any(keyword in placeholder for keyword in ['address', 'neighborhood', 'city', 'zip']):
                            # Make sure it's not a filter
                            if 'price' not in placeholder and 'bed' not in placeholder:
                                search_box = inp
                                logger.info(f"[LocationSearcher] Found Zillow FSBO search box by placeholder: {placeholder}")
                                break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "input[placeholder*='Address, neighborhood']",
                    "input[placeholder*='city']",
                    "input[placeholder*='address']",
                    "input[id*='search']",
                    "input[name*='search']",
                    "input[aria-label*='search']",
                    "input[class*='search']"
                ]
                
                for selector in search_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                search_box = elem
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                raise TimeoutException("Search box not found on Zillow FSBO")
            
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)
            
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "div[class*='suggestion'], li[class*='suggestion'], ul[class*='autocomplete'] li, div[role='option']")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button[aria-label*='search'], button[class*='search']")
                        submit_btn.click()
                    except:
                        search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Zillow FSBO final URL: {current_url}")
            
            if 'zillow.com' in current_url:
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Zillow FSBO search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Zillow FSBO: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_zillow_frbo(cls, location: str) -> Optional[str]:
        """Search Zillow FRBO for a location using their search box."""
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Zillow FRBO for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.zillow.com/homes/for_rent/")
            time.sleep(3)  # Wait for page to load
            
            wait = WebDriverWait(driver, 15)
            # Zillow FRBO uses placeholder "Address, neighborhood, city, ZIP"
            # First try to find by placeholder text
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        # Zillow placeholder: "Address, neighborhood, city, ZIP"
                        if any(keyword in placeholder for keyword in ['address', 'neighborhood', 'city', 'zip']):
                            # Make sure it's not a filter
                            if 'price' not in placeholder and 'bed' not in placeholder:
                                search_box = inp
                                logger.info(f"[LocationSearcher] Found Zillow FRBO search box by placeholder: {placeholder}")
                                break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "input[placeholder*='Address, neighborhood']",
                    "input[placeholder*='city']",
                    "input[placeholder*='address']",
                    "input[id*='search']",
                    "input[name*='search']",
                    "input[aria-label*='search']",
                    "input[class*='search']"
                ]
                
                for selector in search_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                search_box = elem
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                raise TimeoutException("Search box not found on Zillow FRBO")
            
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)
            
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "div[class*='suggestion'], li[class*='suggestion'], ul[class*='autocomplete'] li, div[role='option']")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button[aria-label*='search'], button[class*='search']")
                        submit_btn.click()
                    except:
                        search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Zillow FRBO final URL: {current_url}")
            
            if 'zillow.com' in current_url:
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Zillow FRBO search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Zillow FRBO: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_fsbo(cls, location: str) -> Optional[str]:
        """Search ForSaleByOwner.com for a location using their search box."""
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching FSBO for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.forsalebyowner.com")
            time.sleep(2)  # Wait for page to load
            
            wait = WebDriverWait(driver, 15)
            # FSBO uses placeholder "Search our exclusive home inventory. Enter an address, neighborhood, or city"
            # First try to find by placeholder text
            search_box = None
            try:
                all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = (inp.get_attribute('placeholder') or '').lower()
                        # FSBO placeholder contains: "Search our exclusive home inventory" or "address, neighborhood, or city"
                        if any(keyword in placeholder for keyword in ['search our', 'exclusive home', 'address', 'neighborhood', 'city']):
                            search_box = inp
                            logger.info(f"[LocationSearcher] Found FSBO search box by placeholder: {placeholder[:50]}...")
                            break
            except:
                pass
            
            # Fallback to other selectors
            if not search_box:
                search_selectors = [
                    "input[placeholder*='Search our exclusive']",
                    "input[placeholder*='address, neighborhood']",
                    "input[placeholder*='city']",
                    "input[placeholder*='search']",
                    "input[id*='search']",
                    "input[name*='search']",
                    "input[aria-label*='search']",
                    "input[class*='search']"
                ]
                
                for selector in search_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                search_box = elem
                                break
                        if search_box:
                            break
                    except:
                        continue
            
            if not search_box:
                raise TimeoutException("Search box not found on FSBO")
            
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)
            
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "div[class*='suggestion'], li[class*='suggestion'], ul[class*='autocomplete'] li, div[role='option']")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button[aria-label*='search'], button[class*='search']")
                        submit_btn.click()
                    except:
                        search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] FSBO final URL: {current_url}")
            
            if 'forsalebyowner.com' in current_url:
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for FSBO search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching FSBO: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
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
