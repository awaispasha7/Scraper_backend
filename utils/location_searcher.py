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
        Enters the location, clicks submit, and returns the resulting URL.
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.trulia.com")
            time.sleep(2)  # Wait for page to load
            
            # Wait for search box - Trulia uses placeholder "Search for City, Neighborhood, Zip, County, School"
            wait = WebDriverWait(driver, 15)
            search_selectors = [
                "input[placeholder*='Search for City']",
                "input[placeholder*='City, Neighborhood']",
                "input[type='text'][name*='search']",
                "input[id*='search']",
                "input[class*='search']",
                "input[aria-label*='search']"
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except:
                    continue
            
            if not search_box:
                raise TimeoutException("Search box not found on Trulia")
            
            # Clear and enter location
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)  # Wait for autocomplete suggestions
            
            # Try to click submit button or press Enter
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='submit search'], button[type='submit'], button[class*='submit']")
                submit_button.click()
            except:
                # Fallback to Enter key
                search_box.send_keys(Keys.RETURN)
            
            # Wait for page to load/redirect
            time.sleep(4)
            
            # Get the current URL after search
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Trulia final URL: {current_url}")
            
            # Extract the listing URL format
            if 'trulia.com' in current_url:
                # Build for_sale URL if needed
                match = re.search(r'/([A-Z]{2})/([^/?]+)', current_url)
                if match:
                    state = match.group(1)
                    city = match.group(2)
                    if '/for_sale/' not in current_url:
                        listing_url = f"https://www.trulia.com/for_sale/{state}/{city}/SINGLE-FAMILY_HOME_type/"
                        logger.info(f"[LocationSearcher] Built Trulia listing URL: {listing_url}")
                        return listing_url
                    elif '/SINGLE-FAMILY_HOME_type/' not in current_url:
                        return f"{current_url.rstrip('/')}/SINGLE-FAMILY_HOME_type/"
                
                return current_url
            
            return None
            
        except TimeoutException:
            logger.error(f"[LocationSearcher] Timeout waiting for Trulia search box")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Trulia: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_apartments(cls, location: str) -> Optional[str]:
        """
        Search Apartments.com for a location using their search box.
        Enters the location, clicks search, and returns the resulting URL.
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Apartments.com for: {location_clean}")
            
            driver = cls._get_driver()
            driver.get("https://www.apartments.com")
            time.sleep(2)  # Wait for page to load
            
            # Wait for search box - Apartments.com has textbox with name "Location, School, or Point of Interest"
            wait = WebDriverWait(driver, 15)
            search_selectors = [
                "input[aria-label*='Location']",
                "input[placeholder*='Location']",
                "input[type='text'][name*='search']",
                "input[id*='search']",
                "input[class*='search']",
                "input[aria-label*='search']",
                "input[type='text']"
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    # Find the one that's actually visible and in the search area
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
            
            # Clear and enter location
            search_box.clear()
            search_box.send_keys(location_clean)
            time.sleep(2)  # Wait for autocomplete suggestions
            
            # Try to click on first suggestion if available
            try:
                suggestions = driver.find_elements(By.CSS_SELECTOR, "ul[class*='autocomplete'] li, ul[class*='suggestion'] li, div[class*='suggestion'], li[class*='suggestion']")
                if suggestions:
                    suggestions[0].click()
                    time.sleep(3)
                else:
                    # Click search button or press Enter
                    try:
                        search_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Search apartments'], button[type='submit'], button[class*='search']")
                        search_button.click()
                    except:
                        search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
            except:
                # Fallback to Enter key
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            # Get the current URL after search
            current_url = driver.current_url
            logger.info(f"[LocationSearcher] Apartments.com final URL: {current_url}")
            
            if 'apartments.com' in current_url:
                # Build for-rent-by-owner URL if needed
                match = re.search(r'apartments\.com/([a-z0-9-]+(?:-[a-z]{2})?)/', current_url.lower())
                if match:
                    city_state = match.group(1)
                    if '/for-rent-by-owner/' not in current_url:
                        listing_url = f"https://www.apartments.com/{city_state}/for-rent-by-owner/"
                        logger.info(f"[LocationSearcher] Built Apartments.com listing URL: {listing_url}")
                        return listing_url
                
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
            
            # Wait for search box
            wait = WebDriverWait(driver, 15)
            search_selectors = [
                "input[type='text'][placeholder*='city']",
                "input[type='text'][placeholder*='address']",
                "input[id*='search']",
                "input[name*='search']",
                "input[aria-label*='search']",
                "input[class*='search']"
            ]
            
            search_box = None
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
            time.sleep(2)  # Wait for page to load
            
            wait = WebDriverWait(driver, 15)
            search_selectors = [
                "input[type='text'][placeholder*='city']",
                "input[type='text'][placeholder*='search']",
                "input[id*='search']",
                "input[name*='search']",
                "input[aria-label*='search']",
                "input[class*='search']"
            ]
            
            search_box = None
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
                raise TimeoutException("Search box not found on Hotpads")
            
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
            search_selectors = [
                "input[type='text'][placeholder*='city']",
                "input[type='text'][placeholder*='address']",
                "input[id*='search']",
                "input[name*='search']",
                "input[aria-label*='search']",
                "input[class*='search']",
                "input[type='text']"
            ]
            
            search_box = None
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
            search_selectors = [
                "input[type='text'][placeholder*='city']",
                "input[type='text'][placeholder*='address']",
                "input[id*='search']",
                "input[name*='search']",
                "input[aria-label*='search']",
                "input[class*='search']",
                "input[type='text']"
            ]
            
            search_box = None
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
            search_selectors = [
                "input[type='text'][placeholder*='city']",
                "input[type='text'][placeholder*='search']",
                "input[id*='search']",
                "input[name*='search']",
                "input[aria-label*='search']",
                "input[class*='search']",
                "input[type='text']"
            ]
            
            search_box = None
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
