"""
Selenium-based Scraper for ForSaleByOwner.com
Handles JavaScript-rendered content
Extracts: address, price, beds, baths, square feet, listing link, time of post
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
try:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False
import json
import csv
import time
import logging
from typing import Dict, List, Optional
import re
from urllib.parse import urljoin
import requests
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ForSaleByOwnerSeleniumScraper:
    """Selenium-based scraper for ForSaleByOwner.com listings."""
    
    def __init__(self, base_url: str, headless: bool = True, delay: float = 2.0, api_url: Optional[str] = None):
        """
        Initialize the scraper with Selenium.
        
        Args:
            base_url: Base URL of the search page
            headless: Run browser in headless mode (default: True)
            delay: Delay between actions in seconds (default: 2.0)
            api_url: API URL for real-time storage (default: http://localhost:3000/api/listings/add)
        """
        self.base_url = base_url
        self.delay = delay
        self.driver = None
        # API URL for real-time storage (can be set via environment variable)
        self.api_url = api_url or os.getenv('API_URL', 'http://localhost:3000/api/listings/add')
        self.real_time_storage = os.getenv('REAL_TIME_STORAGE', 'true').lower() == 'true'
        self.setup_driver(headless)
    
    def setup_driver(self, headless: bool = True):
        """Setup Chrome WebDriver."""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Suppress SSL errors and logging
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')
            chrome_options.add_argument('--ignore-certificate-errors-spki-list')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--log-level=3')  # Only show fatal errors
            chrome_options.add_argument('--silent')
            
            # Disable unnecessary services that cause SSL errors
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-breakpad')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-component-update')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-domain-reliability')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--metrics-recording-only')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--safebrowsing-disable-auto-update')
            chrome_options.add_argument('--enable-automation')
            chrome_options.add_argument('--password-store=basic')
            chrome_options.add_argument('--use-mock-keychain')
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set logging preferences to suppress warnings
            prefs = {
                "logging": {
                    "prefs": {
                        "logging.level": "OFF"
                    }
                }
            }
            chrome_options.add_experimental_option('prefs', prefs)
            
            # Try to use webdriver-manager if available, otherwise use system ChromeDriver
            # Suppress ChromeDriver service logs
            service_args = []
            if USE_WEBDRIVER_MANAGER:
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    service.service_args = service_args
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception:
                    # Fallback to system ChromeDriver
                    service = Service()
                    service.service_args = service_args
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Use system ChromeDriver (Selenium 4+ auto-manages it)
                service = Service()
                service.service_args = service_args
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            self.driver.maximize_window()
            logger.info("Chrome WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            logger.error("Make sure Google Chrome browser is installed")
            logger.error("Selenium 4+ should automatically manage ChromeDriver")
            logger.error("If issues persist, install ChromeDriver manually from: https://chromedriver.chromium.org/")
            raise
    
    def wait_for_content(self, timeout: int = 30):
        """Wait for page content to load."""
        try:
            # Wait for the app div to be populated
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(3)  # Additional wait for React to render
            
            # Try to find any listing-related elements
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            logger.info("Page content loaded")
            return True
            
        except TimeoutException:
            logger.warning("Timeout waiting for content to load")
            return False
    
    def extract_price(self, text: str) -> Optional[str]:
        """Extract price from text. Returns formatted price like $665,000."""
        # FIXED: Handle format "$665,0004 Beds" - stop before digits that are part of beds
        price_patterns = [
            r'\$[\d,]+(?=\s*[A-Za-z]|\s+\d|\s*$)',  # $665,000 before "4 Beds" or end - FIXED
            r'\$\s*[\d,]+(?:\.\d+)?[MK]?',  # $665,000 or $665000 or $665K
            r'\$\d{1,3}(?:,\d{3})*(?:\.\d+)?',  # $665,000 format
            r'\$\s*\d+(?:,\d{3})*',  # $665000 or $665,000
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, text)
            if price_match:
                price_str = price_match.group(0).strip()
                # Clean up: remove extra spaces, ensure proper format
                price_str = price_str.replace(' ', '')
                
                # Check if price ends with digits that might be from "Beds" field
                # Example: "$665,0004" should be "$665,000" if followed by " Beds"
                match_end = price_match.end()
                if match_end < len(text):
                    next_chars = text[match_end:match_end+10]
                    # If next is space+digit+letter (like " 4 Beds"), trim trailing digits from price
                    if re.match(r'\s+\d+[A-Za-z]', next_chars):
                        # Remove last digit if price is too long (likely has beds number)
                        if len(price_str) > 8:  # "$665,000" is 8 chars, "$665,0004" is 9
                            price_str = price_str[:-1]  # Remove last digit
                
                # Format: ensure comma separation for thousands
                if ',' not in price_str and len(price_str) > 4:
                    # Add comma for thousands: $665000 -> $665,000
                    numbers = re.search(r'\d+', price_str)
                    if numbers:
                        num_str = numbers.group(0)
                        if len(num_str) > 3:
                            formatted = f"${num_str[:-3]},{num_str[-3:]}"
                            return formatted
                return price_str
        
        return None
    
    def extract_number(self, text: str) -> Optional[str]:
        """Extract number from text."""
        number_match = re.search(r'\d+', text)
        return number_match.group(0) if number_match else None
    
    def extract_square_feet(self, text: str) -> Optional[str]:
        """Extract square feet from text."""
        sqft_match = re.search(r'([\d,]+)\s*(?:sq|square)\s*(?:ft|feet)', text, re.IGNORECASE)
        if sqft_match:
            return sqft_match.group(1).replace(',', '')
        return None
    
    def scroll_page(self):
        """Scroll page to load more content."""
        try:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Scroll back up a bit
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error scrolling page: {e}")
    
    def send_listing_to_api(self, listing_data: Dict) -> bool:
        """
        Send a single listing to the API for real-time storage in Supabase.
        
        Args:
            listing_data: Dictionary with listing information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"📤 Sending listing to API: {self.api_url}")
            logger.info(f"   Address: {listing_data.get('address', 'N/A')[:50]}")
            
            response = requests.post(
                self.api_url,
                json=listing_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            logger.info(f"📥 API Response: Status {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    action = result.get('action', 'unknown')
                    if action == 'added':
                        logger.info(f"💾 ✅ Stored in database (NEW): {listing_data.get('address', 'N/A')[:50]}")
                    elif action == 'updated':
                        logger.info(f"💾 ✅ Stored in database (UPDATED): {listing_data.get('address', 'N/A')[:50]}")
                    elif result.get('skipped'):
                        logger.info(f"⏭️ Skipped (suburb): {listing_data.get('address', 'N/A')[:50]}")
                    return True
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"❌ API returned success=false: {error_msg}")
                    # If it's a database schema error, log it prominently
                    if 'does not exist' in error_msg or 'table' in error_msg.lower():
                        logger.error(f"⚠️ DATABASE SCHEMA ERROR: {error_msg}")
                        logger.error(f"⚠️ Please run supabase_schema.sql in your Supabase SQL Editor")
                    return False
            else:
                error_text = response.text[:500]
                logger.error(f"❌ API returned status {response.status_code}: {error_text}")
                return False
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Cannot connect to API at {self.api_url}")
            logger.error(f"   Make sure Next.js server is running on http://localhost:3000")
            logger.error(f"   Error: {e}")
            return False
        except requests.exceptions.Timeout as e:
            logger.warning(f"⚠️ API request timeout: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send listing to API: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error sending listing to API: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def get_already_scraped_urls(self) -> set:
        """
        Get URLs of listings that were already scraped in previous runs.
        
        Returns:
            Set of listing URLs that were already scraped
        """
        import os
        import json
        
        scraped_urls = set()
        json_file = 'forsalebyowner_listings.json'
        
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    
                # Handle both old format (list) and new format (with metadata)
                if isinstance(old_data, dict) and 'listings' in old_data:
                    old_listings = old_data['listings']
                else:
                    old_listings = old_data
                
                # Extract all listing URLs
                for listing in old_listings:
                    url = listing.get('listing_link', '')
                    if url:
                        scraped_urls.add(url)
                
                logger.info(f"Found {len(scraped_urls)} already scraped listings to skip")
            except Exception as e:
                logger.error(f"Error reading previous data: {e}")
        
        return scraped_urls
    
    def scrape_listings(self, skip_existing: bool = True) -> List[Dict]:
        """
        Scrape all listings from the current page.
        
        Args:
            skip_existing: If True, skip listings that were already scraped
        
        Returns:
            List of dictionaries with listing data (only new listings if skip_existing=True)
        """
        listings = []
        
        # Get already scraped URLs if we should skip them
        already_scraped = set()
        if skip_existing:
            already_scraped = self.get_already_scraped_urls()
            if already_scraped:
                logger.info(f"Skipping {len(already_scraped)} already scraped listings")
        
        try:
            # Navigate to the page
            logger.info(f"🌐 Navigating to: {self.base_url}")
            logger.info(f"💾 Real-time storage: {'ENABLED' if self.real_time_storage else 'DISABLED'}")
            logger.info(f"🔗 API URL: {self.api_url}")
            self.driver.get(self.base_url)
            
            # Wait for content to load
            logger.info("⏳ Waiting for page content to load...")
            if not self.wait_for_content():
                logger.error("❌ Failed to load page content")
                return []
            logger.info("✅ Page content loaded successfully")
            
            # Scroll multiple times to load all content
            for i in range(3):
                self.scroll_page()
                time.sleep(2)
            
            # Try to click "View More Listings" button or load more content
            # IMPORTANT: Keep clicking until we get 132 listings
            max_clicks = 20  # Increased from 10 to 20 for 132 listings
            previous_link_count = 0
            no_progress_count = 0  # Track consecutive clicks with no progress
            
            for click_attempt in range(max_clicks):
                try:
                    # Count current UNIQUE links before clicking
                    all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/listing/']")
                    unique_hrefs = set()
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            if href:
                                unique_hrefs.add(href)
                        except:
                            continue
                    current_links = len(unique_hrefs)
                    logger.info(f"Current UNIQUE listing links found: {current_links} (Expected: 132)")
                    
                    # Check if we've reached the expected count (132 listings)
                    if current_links >= 132:
                        logger.info(f"✅ Reached expected count of 132 listings! Stopping 'View More' clicks.")
                        break
                    
                    # Check if no progress made
                    if current_links == previous_link_count and click_attempt > 0:
                        no_progress_count += 1
                        if no_progress_count >= 2:
                            logger.warning(f"No new listings loaded after {no_progress_count} attempts (still at {current_links})")
                            logger.warning(f"Only found {current_links} listings, expected 132. Will continue with available listings.")
                            break
                    else:
                        no_progress_count = 0
                    
                    previous_link_count = current_links
                    
                    # Scroll to bottom first to ensure button is visible
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Try finding "View More Listings" button - it's an <a> tag, not <button>
                    view_more_button = None
                    
                    # Method 1: Find by text content (most reliable) - check <a> tags first
                    try:
                        all_links_elements = self.driver.find_elements(By.TAG_NAME, "a")
                        all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                        
                        for element in all_links_elements + all_buttons:
                            try:
                                element_text = element.text.strip().lower()
                                if any(phrase in element_text for phrase in ["view more listings", "view more", "load more listings", "load more", "show more listings"]):
                                    # Check if visible and enabled
                                    is_visible = element.is_displayed()
                                    try:
                                        is_enabled = element.is_enabled()
                                    except:
                                        is_enabled = True
                                    
                                    if is_visible and is_enabled:
                                        view_more_button = element
                                        logger.info(f"Found 'View More' button by text: '{element.text.strip()}' (attempt {click_attempt + 1})")
                                        break
                            except:
                                continue
                    except Exception as e:
                        logger.debug(f"Error finding button by text: {e}")
                    
                    # Method 2: Try XPath selectors (prioritize <a> tags)
                    if not view_more_button:
                        xpath_selectors = [
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more listings')]",
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]",
                            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]",
                            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]",
                            "//a[contains(@class, 'more')]",
                            "//button[contains(@class, 'more')]",
                        ]
                        
                        for xpath in xpath_selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, xpath)
                                for elem in elements:
                                    try:
                                        if elem.is_displayed():
                                            view_more_button = elem
                                            logger.info(f"Found 'View More' button by XPath: {xpath[:50]}... (attempt {click_attempt + 1})")
                                            break
                                    except:
                                        continue
                                if view_more_button:
                                    break
                            except:
                                continue
                    
                    # Click button if found
                    if view_more_button:
                        try:
                            # Scroll to button to ensure it's in viewport
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", view_more_button)
                            time.sleep(1.5)
                            
                            # Try JavaScript click first (more reliable for dynamic content)
                            self.driver.execute_script("arguments[0].click();", view_more_button)
                            logger.info(f"✅ Clicked 'View More' button (attempt {click_attempt + 1})")
                            
                            # Wait longer for new listings to load (increased from 4 to 6 seconds)
                            time.sleep(6)
                            
                            # Scroll again to trigger any lazy loading
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(2)
                            
                            # Check if new listings loaded
                            new_all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/listing/']")
                            new_unique_hrefs = set()
                            for link in new_all_links:
                                try:
                                    href = link.get_attribute('href')
                                    if href:
                                        new_unique_hrefs.add(href)
                                except:
                                    continue
                            new_links = len(new_unique_hrefs)
                            
                            if new_links > current_links:
                                logger.info(f"✅ New listings loaded! Count increased from {current_links} to {new_links}")
                                current_links = new_links  # Update current count
                            else:
                                logger.warning(f"⚠️ No new listings detected after click (still {current_links})")
                            
                            # Stop if we've reached 132 listings
                            if new_links >= 132:
                                logger.info(f"✅ Reached target of 132 listings! Stopping button clicks.")
                                break
                        except Exception as e:
                            logger.warning(f"Error clicking button: {e}")
                            # Try regular click as fallback
                            try:
                                view_more_button.click()
                                time.sleep(6)
                            except Exception as e2:
                                logger.warning(f"Regular click also failed: {e2}")
                    else:
                        logger.warning(f"⚠️ No 'View More' button found (attempt {click_attempt + 1})")
                        # Try scrolling more to trigger lazy loading
                        logger.info("Trying additional scrolling to trigger lazy loading...")
                        for i in range(5):
                            self.driver.execute_script(f"window.scrollTo(0, {i * 1000});")
                            time.sleep(1)
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(3)
                        
                        # Check if scrolling loaded more content
                        final_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/listing/']")
                        final_unique = set()
                        for link in final_links:
                            try:
                                href = link.get_attribute('href')
                                if href:
                                    final_unique.add(href)
                            except:
                                continue
                        if len(final_unique) > current_links:
                            logger.info(f"Scrolling loaded more listings: {len(final_unique)}")
                        else:
                            logger.warning("No more listings found after scrolling. Stopping.")
                            break
                    
                except Exception as e:
                    logger.error(f"Error in 'View More' loop (attempt {click_attempt + 1}): {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    # Continue trying instead of breaking
                    time.sleep(2)
            
            # Final scroll to load any lazy-loaded content
            logger.info("Performing final scroll to load all content...")
            for i in range(5):
                self.driver.execute_script(f"window.scrollTo(0, {i * 1000});")
                time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Count final UNIQUE listing links - try multiple times to ensure all are loaded
            logger.info("Counting final unique listing links...")
            max_attempts = 3
            final_unique_hrefs = set()
            
            for attempt in range(max_attempts):
                all_final_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/listing/']")
                for link in all_final_links:
                    try:
                        href = link.get_attribute('href')
                        if href and '/listing/' in href:
                            final_unique_hrefs.add(href)
                    except:
                        continue
                
                final_links = len(final_unique_hrefs)
                logger.info(f"Attempt {attempt + 1}: Found {final_links} unique listing links (Expected: 132)")
                
                if final_links >= 132:
                    logger.info(f"✅ Found all 132 listings!")
                    break
                elif attempt < max_attempts - 1:
                    # Scroll more and wait
                    logger.info("Scrolling more to load additional listings...")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)
                    # Try clicking "View More" one more time if button exists
                    try:
                        view_more = self.driver.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more listings')]")
                        if view_more and view_more.is_displayed():
                            self.driver.execute_script("arguments[0].click();", view_more)
                            time.sleep(6)
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(2)
                    except:
                        pass
            
            final_links = len(final_unique_hrefs)
            logger.info(f"Final UNIQUE listing links found: {final_links} (Expected: 132)")
            
            if final_links < 132:
                logger.warning(f"⚠️ Only found {final_links} links, expected 132. Some listings may be missing.")
                logger.warning(f"Will try to scrape all {final_links} available listings.")
            else:
                logger.info(f"✅ Successfully found all 132 listings!")
            
            # NEW APPROACH: Collect ALL unique listing URLs first, then process each one individually
            # This avoids stale element issues by finding elements fresh for each URL
            logger.info("Collecting ALL unique listing URLs...")
            all_listing_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/listing/']")
            logger.info(f"Found {len(all_listing_links)} total listing link elements")
            
            # Collect unique URLs
            unique_urls = set()
            for link in all_listing_links:
                try:
                    href = link.get_attribute('href')
                    if href and '/listing/' in href:
                        unique_urls.add(href)
                except:
                    continue
            
            logger.info(f"Found {len(unique_urls)} unique listing URLs (Expected: 132)")
            
            if len(unique_urls) < 132:
                logger.warning(f"⚠️ Only found {len(unique_urls)} unique URLs, expected 132. Some listings may be missing.")
            
            if not unique_urls:
                logger.error("No listing URLs found!")
                return []
            
            # Process each URL individually - this avoids stale element issues
            logger.info(f"🔄 Processing {len(unique_urls)} listings individually...")
            logger.info(f"📊 Expected total listings from website: 132")
            logger.info(f"💾 Real-time storage: {'ENABLED - storing in database as we scrape' if self.real_time_storage else 'DISABLED - will store after scraping'}")
            new_count = 0
            skipped_count = 0
            current_url = self.driver.current_url  # Save current URL to return to
            
            for i, listing_url in enumerate(unique_urls, 1):
                try:
                    # Show progress every 10 listings
                    if i % 10 == 0 or i == 1:
                        logger.info(f"Processing listing {i}/{len(unique_urls)}...")
                    
                    # Check if this listing was already scraped
                    if skip_existing and listing_url in already_scraped:
                        skipped_count += 1
                        if skipped_count % 20 == 0 or skipped_count == 1:
                            logger.info(f"Skipped {skipped_count} already scraped listings...")
                        continue
                    
                    # Initialize listing data
                    listing_data = {
                        'address': None,
                        'price': None,
                        'beds': None,
                        'baths': None,
                        'square_feet': None,
                        'listing_link': listing_url,
                        'time_of_post': None
                    }
                    
                    # Extract address from URL first
                    try:
                        url_parts = listing_url.split('/listing/')
                        if len(url_parts) > 1:
                            address_part = url_parts[1].split('/')[0]
                            address = address_part.replace('-', ' ').title()
                            listing_data['address'] = address
                    except:
                        pass
                    
                    # Try to get data from search results page first (faster)
                    # Also check if property is sold on search page
                    is_sold_on_search_page = False
                    try:
                        # Re-find the link element fresh (avoids stale element)
                        link_elem = self.driver.find_element(By.CSS_SELECTOR, f"a[href='{listing_url}']")
                        if link_elem:
                            # Find parent card fresh
                            for level in range(1, 15):
                                try:
                                    parent = link_elem.find_element(By.XPATH, f"./ancestor::*[{level}]")
                                    parent_text = self._safe_get_element_text(parent).strip()
                                    
                                    # Check if property is sold on search page
                                    if self.is_property_sold(parent_text):
                                        logger.info(f"⏭️  SKIPPED (SOLD on search page): {listing_data.get('address', 'N/A')[:50]}")
                                        is_sold_on_search_page = True
                                        break  # Break out of level loop
                                    
                                    if len(parent_text) > 100:
                                        # Try to parse this parent card
                                        parsed_data = self.parse_listing_element(parent)
                                        if parsed_data.get('listing_link') == listing_url:
                                            # Use parsed data if we got it
                                            if parsed_data.get('price'):
                                                listing_data['price'] = parsed_data.get('price')
                                            if parsed_data.get('beds'):
                                                listing_data['beds'] = parsed_data.get('beds')
                                            if parsed_data.get('baths'):
                                                listing_data['baths'] = parsed_data.get('baths')
                                            if parsed_data.get('square_feet'):
                                                listing_data['square_feet'] = parsed_data.get('square_feet')
                                            if parsed_data.get('address'):
                                                listing_data['address'] = parsed_data.get('address')
                                            break
                                except:
                                    continue
                    except Exception as e:
                        logger.debug(f"Could not parse from search page for {listing_url[:50]}...: {e}")
                    
                    # Skip if sold on search page
                    if is_sold_on_search_page:
                        continue  # Skip this listing entirely
                    
                    # ALWAYS visit individual page to get ACTUAL prices and complete data
                    # This ensures we get real prices instead of "Price on Request"
                    logger.debug(f"Visiting individual page to fetch actual price and complete data: {listing_url[:60]}...")
                    page_details = self.fetch_listing_details(listing_url)
                    
                    # Skip sold properties - don't add them to listings
                    if page_details.get('is_sold'):
                        logger.info(f"⏭️  SKIPPED (SOLD): {listing_data.get('address', 'N/A')[:50]}")
                        # Return to search results page
                        try:
                            self.driver.get(current_url)
                            time.sleep(1)
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                        except:
                            pass
                        continue  # Skip this listing, don't add it
                    
                    # ALWAYS use data from individual page (more reliable and complete)
                    # Only keep search page data if individual page doesn't have it
                    if page_details.get('price') and page_details.get('price') not in [None, 'null', 'None', '']:
                        listing_data['price'] = page_details.get('price')
                        logger.debug(f"✓ Got actual price from listing page: {page_details.get('price')}")
                    elif not listing_data.get('price') or 'request' in str(listing_data.get('price', '')).lower():
                        # If still no price, keep trying
                        if page_details.get('price'):
                            listing_data['price'] = page_details.get('price')
                    
                    # Use individual page data for beds, baths, sqft if available
                    if page_details.get('beds'):
                        listing_data['beds'] = page_details.get('beds')
                    if page_details.get('baths'):
                        listing_data['baths'] = page_details.get('baths')
                    if page_details.get('square_feet'):
                        listing_data['square_feet'] = page_details.get('square_feet')
                    if page_details.get('time_of_post'):
                        listing_data['time_of_post'] = page_details.get('time_of_post')
                    
                    # Return to search results page
                    try:
                        self.driver.get(current_url)
                        time.sleep(1)
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                    except:
                        pass
                    
                    # Only add non-sold properties to listings
                    if listing_data.get('address') or listing_data.get('listing_link'):
                        listings.append(listing_data)
                        new_count += 1
                        
                        # REAL-TIME STORAGE: Send to Supabase immediately as we scrape
                        if self.real_time_storage:
                            try:
                                success = self.send_listing_to_api(listing_data)
                                if not success:
                                    logger.warning(f"⚠️ Failed to store listing in database (will sync later)")
                            except Exception as e:
                                logger.error(f"❌ Exception sending listing to API: {e}")
                                import traceback
                                logger.debug(traceback.format_exc())
                        
                        # Log with data completeness
                        data_status = []
                        if listing_data.get('price'): data_status.append('P')
                        if listing_data.get('beds'): data_status.append('B')
                        if listing_data.get('baths'): data_status.append('A')
                        if listing_data.get('square_feet'): data_status.append('S')
                        status_str = ''.join(data_status) if data_status else 'NO DATA'
                        logger.info(f"✅ Listing {new_count}: {listing_data.get('address', 'N/A')[:50]} [{status_str}]")
                except Exception as e:
                    logger.error(f"Error processing listing {i} ({listing_url[:50]}...): {e}")
                    # Return to search page even on error
                    try:
                        self.driver.get(current_url)
                        time.sleep(1)
                    except:
                        pass
                    continue
            
            logger.info(f"Total unique URLs processed: {len(unique_urls)}")
            if skip_existing:
                logger.info(f"Summary: {new_count} NEW listings, {skipped_count} already scraped (skipped)")
            else:
                logger.info(f"Summary: {len(listings)} total listings processed")
            
        except Exception as e:
            logger.error(f"Error scraping listings: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return listings
    
    def is_property_sold(self, page_text: str) -> bool:
        """
        Check if property is sold by looking for sold indicators in page text.
        
        Args:
            page_text: Full text content of the listing page or card
            
        Returns:
            True if property is sold, False otherwise
        """
        if not page_text:
            return False
        
        sold_indicators = [
            'sold',
            'this property has been sold',
            'property sold',
            'no longer available',
            'listing removed',
            'off market',
            'status: sold',
            'sold status',
            'property is sold',
            'has been sold',
            'sold property',
            'not available',
            'unavailable',
            'removed from market',
        ]
        
        page_text_lower = page_text.lower()
        for indicator in sold_indicators:
            if indicator in page_text_lower:
                return True
        
        return False
    
    def fetch_listing_details(self, listing_url: str) -> Dict:
        """
        Visit individual listing page to fetch complete details.
        Used when search results page doesn't have all data.
        
        Args:
            listing_url: URL of the individual listing page
            
        Returns:
            Dictionary with extracted data from listing page
            Returns {'is_sold': True} if property is sold
        """
        details = {
            'price': None,
            'beds': None,
            'baths': None,
            'square_feet': None,
            'time_of_post': None,
            'is_sold': False
        }
        
        try:
            logger.debug(f"Fetching details from listing page: {listing_url}")
            self.driver.get(listing_url)
            time.sleep(2)  # Reduced wait time from 3 to 2 seconds
            
            # Wait for page to load with timeout - wait longer for content
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # Additional wait for dynamic content to load
                time.sleep(2)
            except:
                time.sleep(3)  # Fallback wait
            
            # Scroll to ensure content is loaded
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
            except:
                pass
            
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Check for sold indicators in page elements (more reliable)
            sold_found = False
            try:
                # Check for sold badges/labels using CSS selectors
                sold_selectors = [
                    "[class*='sold']",
                    "[class*='Sold']",
                    "[data-status*='sold']",
                ]
                for selector in sold_selectors:
                    try:
                        sold_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if sold_elements:
                            for elem in sold_elements:
                                elem_text = elem.text.lower()
                                if 'sold' in elem_text:
                                    sold_found = True
                                    break
                        if sold_found:
                            break
                    except:
                        continue
                
                # Also check using XPath for text containing "Sold"
                if not sold_found:
                    try:
                        sold_xpath = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sold')]"
                        sold_elements = self.driver.find_elements(By.XPATH, sold_xpath)
                        if sold_elements:
                            for elem in sold_elements:
                                elem_text = elem.text.lower()
                                # Check if it's actually about the property being sold
                                if 'sold' in elem_text and any(word in elem_text for word in ['property', 'listing', 'home', 'house', 'this']):
                                    sold_found = True
                                    break
                    except:
                        pass
            except:
                pass
            
            # Check if property is sold - if sold, skip it
            if sold_found or self.is_property_sold(page_text):
                logger.info(f"⏭️  Property is SOLD, skipping: {listing_url[:60]}...")
                details['is_sold'] = True
                return details
            
            # Extract price from listing page - try specific selectors first
            # IMPORTANT: Skip "Price Last Listed At" - that's for sold properties
            # We want the CURRENT listing price, not the old sold price
            price_selectors = [
                "h1 span",  # Price often in h1 tag
                "h2 span",  # Or h2 tag
                "div[class*='price'] span",  # Price div
                "span[class*='text-xl']",  # Common: "block text-xl" or "text-xl"
                "span[class*='text-2xl']",  # Larger size
                "span[class*='text-3xl']",  # Even larger
                "div[class*='font-bold'] span",  # In bold div
                "[class*='price']", "[class*='Price']",
                "[data-testid*='price']",
                "div[class*='text-center'] span",  # Center aligned
            ]
            
            for selector in price_selectors:
                try:
                    price_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for price_elem in price_elems:
                        price_text = price_elem.text.strip()
                        # SKIP if it contains "Last Listed" or "Sold" - that's old/sold price
                        if 'last listed' in price_text.lower() or 'sold' in price_text.lower():
                            continue
                        if price_text and '$' in price_text:
                            # Extract just the price part - handle formats like "$665,000" or "$665000"
                            price_match = re.search(r'\$[\d,]+', price_text)
                            if price_match:
                                price_val = price_match.group(0)
                                # Validate it's a real price (not too small)
                                num_str = price_val.replace('$', '').replace(',', '')
                                if num_str.isdigit() and int(num_str) > 100:  # At least $100
                                    details['price'] = price_val
                                    logger.debug(f"Found price via selector {selector}: {price_val}")
                                    break
                    if details['price']:
                        break
                except:
                    continue
            
            # Fallback to regex patterns - more comprehensive
            # IMPORTANT: Prioritize current price, skip "Price Last Listed At" and "Sold Price"
            if not details['price']:
                # First, try to find CURRENT listing price (not sold/old price)
                current_price_patterns = [
                    r'List\s+Price:\s*\$?([\d,]+)',  # List Price: $665,000
                    r'Asking\s+Price:\s*\$?([\d,]+)',  # Asking Price: $665,000
                    r'Price[:\s]+(\$?[\d,]+)',  # Price: $665,000 (but NOT "Price Last Listed At")
                ]
                
                for pattern in current_price_patterns:
                    price_match = re.search(pattern, page_text, re.IGNORECASE)
                    if price_match:
                        # Check context - skip if it's "Price Last Listed At" or "Sold Price"
                        match_start = price_match.start()
                        context_start = max(0, match_start - 50)
                        context = page_text[context_start:match_start + 50].lower()
                        if 'last listed' in context or 'sold price' in context:
                            continue
                        if price_match.lastindex and price_match.lastindex > 0:
                            price_str = price_match.group(1)
                        else:
                            price_str = price_match.group(0)
                        # Clean and format price
                        price_cleaned = price_str.replace('$', '').replace(',', '').strip()
                        if price_cleaned and price_cleaned.isdigit():
                            num = int(price_cleaned)
                            if num > 100:  # Valid price (at least $100)
                                details['price'] = f"${num:,}"
                                logger.debug(f"Found current price via regex: {details['price']}")
                                break
                
                # If still no price, try generic pattern but validate it's not sold/old price
                if not details['price']:
                    # Find all price matches and pick the largest one (usually the current listing price)
                    all_prices = re.findall(r'\$([\d,]+)', page_text)
                    valid_prices = []
                    for price_str in all_prices:
                        price_cleaned = price_str.replace(',', '').strip()
                        if price_cleaned.isdigit():
                            num = int(price_cleaned)
                            if num > 100 and num < 100000000:  # Reasonable range
                                valid_prices.append(num)
                    
                    if valid_prices:
                        # Use the largest price (usually the current listing price, not old/sold price)
                        max_price = max(valid_prices)
                        details['price'] = f"${max_price:,}"
                        logger.debug(f"Found price (max of all prices): {details['price']}")
            
            # Extract beds - try specific selectors first
            beds_selectors = [
                "span[class*='px-2']",  # Common: "px-2" class
                "div[class*='text-sm'] span:first-child",  # First span in text-sm div
                "[class*='bed']", "[class*='Bed']",
            ]
            
            for selector in beds_selectors:
                try:
                    beds_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for beds_elem in beds_elems:
                        beds_text = beds_elem.text.strip()
                        if 'bed' in beds_text.lower() and not 'bath' in beds_text.lower():
                            beds_match = re.search(r'(\d+)\s*(?:bed|beds|br|bedroom|BR|Bed)', beds_text, re.IGNORECASE)
                            if beds_match:
                                details['beds'] = beds_match.group(1)
                                break
                    if details['beds']:
                        break
                except:
                    continue
            
            # Fallback to regex - more comprehensive patterns
            if not details['beds']:
                beds_patterns = [
                    r'(\d+)\s+Beds?',  # 4 Beds
                    r'(\d+)\s+Bedrooms?',  # 4 Bedrooms
                    r'(\d+)\s+BR\b',  # 4 BR
                    r'Bedrooms?[:\s]+(\d+)',  # Bedrooms: 4
                    r'(\d+)\s*bed\b',  # 4 bed
                ]
                for pattern in beds_patterns:
                    beds_match = re.search(pattern, page_text, re.IGNORECASE)
                    if beds_match:
                        beds_num = beds_match.group(1)
                        if beds_num and int(beds_num) <= 20:  # Valid range
                            details['beds'] = beds_num
                            break
            
            # Extract baths - try specific selectors first
            baths_selectors = [
                "span[class*='border-l'][class*='pl-2']",  # Common: "border-l border-white pl-2"
                "span[class*='pl-2']",  # Has pl-2 class
                "div[class*='text-sm'] span:last-child",  # Last span in text-sm div
                "[class*='bath']", "[class*='Bath']",
            ]
            
            for selector in baths_selectors:
                try:
                    baths_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for baths_elem in baths_elems:
                        baths_text = baths_elem.text.strip()
                        if 'bath' in baths_text.lower() and not 'bed' in baths_text.lower():
                            baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|baths|ba|bathroom|BA|Bath)', baths_text, re.IGNORECASE)
                            if baths_match:
                                details['baths'] = baths_match.group(1)
                                break
                    if details['baths']:
                        break
                except:
                    continue
            
            # Fallback to regex - more comprehensive patterns
            if not details['baths']:
                baths_patterns = [
                    r'(\d+(?:\.\d+)?)\s+Baths?',  # 4 Baths or 2.5 Baths
                    r'(\d+(?:\.\d+)?)\s+Bathrooms?',  # 4 Bathrooms
                    r'(\d+(?:\.\d+)?)\s+BA\b',  # 4 BA
                    r'Bathrooms?[:\s]+(\d+(?:\.\d+)?)',  # Bathrooms: 4
                    r'(\d+(?:\.\d+)?)\s*bath\b',  # 4 bath
                ]
                for pattern in baths_patterns:
                    baths_match = re.search(pattern, page_text, re.IGNORECASE)
                    if baths_match:
                        baths_num = baths_match.group(1)
                        if baths_num:
                            try:
                                if float(baths_num) <= 30:  # Valid range
                                    details['baths'] = baths_num
                                    break
                            except:
                                pass
            
            # Extract square feet - look for "3,125 SqFt" or "Living Area: 3,125 SqFt"
            # IMPORTANT: Get the FULL value, not partial matches (e.g., "4978" not "180")
            sqft_selectors = [
                "span[class*='border-l'][class*='px-3']",  # Common: "border-l border-gray-light px-3"
                "span[class*='border-gray-light']",  # Contains border-gray-light
                "div[class*='text-center'] span",  # In text-center div
                "div[class*='flex'][class*='items-center'] span",  # In flex container
                "[class*='sqft']", "[class*='SqFt']", "[class*='square']",
            ]
            
            for selector in sqft_selectors:
                try:
                    sqft_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for sqft_elem in sqft_elems:
                        sqft_text = sqft_elem.text.strip()
                        if 'sqft' in sqft_text.lower() or 'square' in sqft_text.lower():
                            # Extract FULL number - handle formats like "4,978 SqFt" or "4978 SqFt"
                            # Use more comprehensive pattern to get complete number
                            sqft_match = re.search(r'(\d{1,4}(?:,\d{3})*)\s*(?:sq|square)\s*(?:ft|feet)', sqft_text, re.IGNORECASE)
                            if sqft_match:
                                sqft_val = sqft_match.group(1).replace(',', '')
                                # Validate: square feet should be reasonable (100-50000)
                                if sqft_val.isdigit():
                                    sqft_int = int(sqft_val)
                                    if 100 <= sqft_int <= 50000:
                                        details['square_feet'] = sqft_val
                                        logger.debug(f"Found sqft via selector {selector}: {sqft_val}")
                                        break
                    if details['square_feet']:
                        break
                except:
                    continue
            
            # Try "Living Area" text specifically (common on listing pages)
            if not details['square_feet']:
                try:
                    living_area_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Living Area')]")
                    for elem in living_area_elems:
                        text = elem.text
                        sqft_match = re.search(r'Living\s+Area:\s*(\d{1,4}(?:,\d{3})*)\s+SqFt', text, re.IGNORECASE)
                        if sqft_match:
                            sqft_val = sqft_match.group(1).replace(',', '')
                            if sqft_val.isdigit():
                                sqft_int = int(sqft_val)
                                if 100 <= sqft_int <= 50000:
                                    details['square_feet'] = sqft_val
                                    logger.debug(f"Found sqft via Living Area: {sqft_val}")
                                    break
                except:
                    pass
            
            # Fallback to regex patterns - get FULL value
            if not details['square_feet']:
                sqft_patterns = [
                    r'Living\s+Area:\s*(\d{1,4}(?:,\d{3})*)\s+SqFt',  # "Living Area: 4,978 SqFt"
                    r'(\d{1,4}(?:,\d{3})*)\s+SqFt\b',  # "4,978 SqFt" (word boundary to avoid partial matches)
                    r'(\d{1,4}(?:,\d{3})*)\s+square\s+feet',
                    r'(\d{1,4}(?:,\d{3})*)\s+sq\.?\s*ft\.?',
                ]
                
                for pattern in sqft_patterns:
                    sqft_matches = re.finditer(pattern, page_text, re.IGNORECASE)
                    for sqft_match in sqft_matches:
                        sqft_val = sqft_match.group(1).replace(',', '')
                        if sqft_val.isdigit():
                            sqft_int = int(sqft_val)
                            # Validate: reasonable range (100-50000)
                            # Prefer larger values (likely the actual square feet, not partial matches)
                            if 100 <= sqft_int <= 50000:
                                if not details['square_feet'] or int(details['square_feet']) < sqft_int:
                                    details['square_feet'] = sqft_val
                                    logger.debug(f"Found sqft via regex: {sqft_val}")
                    if details['square_feet']:
                        break
            
            # Try XPath selectors for more specific extraction
            try:
                # Price
                if not details['price']:
                    price_elem = self.driver.find_element(By.XPATH, "//*[contains(text(), '$') and (contains(text(), 'Price') or contains(text(), 'List'))]")
                    if price_elem:
                        price_text = price_elem.text
                        price_match = self.extract_price(price_text)
                        if price_match:
                            details['price'] = price_match
            except:
                pass
            
            # Don't navigate back here - caller will handle it
            
        except Exception as e:
            logger.warning(f"Error fetching details from {listing_url}: {e}")
            # Don't navigate back here - caller will handle it
        
        return details
    
    def _safe_get_element_text(self, element, max_retries=3):
        """Safely get element text, handling stale element references."""
        for attempt in range(max_retries):
            try:
                return element.text
            except Exception as e:
                if 'stale' in str(e).lower() and attempt < max_retries - 1:
                    logger.debug(f"Stale element, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(0.5)
                    continue
                else:
                    raise
        return ""
    
    def _safe_find_element(self, parent, selector, by=By.CSS_SELECTOR, max_retries=3):
        """Safely find element, handling stale element references."""
        for attempt in range(max_retries):
            try:
                if by == By.CSS_SELECTOR:
                    return parent.find_element(By.CSS_SELECTOR, selector)
                elif by == By.XPATH:
                    return parent.find_element(By.XPATH, selector)
            except Exception as e:
                if 'stale' in str(e).lower() and attempt < max_retries - 1:
                    logger.debug(f"Stale element in find, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(0.5)
                    continue
                else:
                    raise
        return None
    
    def parse_listing_element(self, element) -> Dict:
        """
        Parse a single listing element and extract all required data.
        If data is missing, visits individual listing page to get complete details.
        Handles stale element references with retry logic.
        
        Args:
            element: WebElement representing a listing
            
        Returns:
            Dictionary with extracted data
        """
        listing_data = {
            'address': None,
            'price': None,
            'beds': None,
            'baths': None,
            'square_feet': None,
            'listing_link': None,
            'time_of_post': None
        }
        
        try:
            # Get element text with stale element handling
            element_text = self._safe_get_element_text(element)
            
            # Extract address
            address_selectors = [
                "h1", "h2", "h3", "h4",
                ".address", "[data-address]",
                ".property-address", ".listing-address"
            ]
            
            for selector in address_selectors:
                try:
                    addr_elem = self._safe_find_element(element, selector)
                    if addr_elem:
                        address_text = self._safe_get_element_text(addr_elem).strip()
                        if address_text and len(address_text) > 5:
                            listing_data['address'] = address_text
                            break
                except:
                    continue
            
            # If address not found, try to extract from link text
            if not listing_data['address']:
                try:
                    tag_name = element.tag_name if hasattr(element, 'tag_name') else None
                    if tag_name == 'a':
                        listing_data['address'] = self._safe_get_element_text(element).strip()
                    else:
                        link = self._safe_find_element(element, "a")
                        if link:
                            listing_data['address'] = self._safe_get_element_text(link).strip()
                except:
                    pass
            
            # Extract listing link
            try:
                tag_name = element.tag_name if hasattr(element, 'tag_name') else None
                if tag_name == 'a':
                    href = element.get_attribute('href')
                    if href:
                        listing_data['listing_link'] = href
                        # Extract address from URL if not found
                        if not listing_data['address'] and '/listing/' in href:
                            # URL format: /listing/4557-South-Calumet-Avenue-Chicago-IL-60653/...
                            url_parts = href.split('/listing/')
                            if len(url_parts) > 1:
                                address_part = url_parts[1].split('/')[0]
                                # Replace dashes with spaces and format
                                address = address_part.replace('-', ' ').title()
                                listing_data['address'] = address
                else:
                    link = self._safe_find_element(element, "a[href*='/listing/']")
                    if link:
                        href = link.get_attribute('href')
                        if href:
                            listing_data['listing_link'] = href
                            # Extract address from URL if not found
                            if not listing_data['address'] and '/listing/' in href:
                                url_parts = href.split('/listing/')
                                if len(url_parts) > 1:
                                    address_part = url_parts[1].split('/')[0]
                                    address = address_part.replace('-', ' ').title()
                                    listing_data['address'] = address
            except:
                pass
            
            # Extract price - FIXED for website format: "$665,0004 Beds" (no space after price)
            # Price appears in: <span class="block text-xl">$665,000</span>
            # Try specific selectors first (most reliable)
            price_selectors = [
                "span.block.text-xl",  # Exact match: "block text-xl"
                "span[class*='text-xl']",  # Contains "text-xl"
                "span[class*='text-2xl']",  # Alternative size
                "span[class*='text-lg']",   # Smaller size
                "div[class*='text-right'] span",  # Price in right-aligned div
                "[class*='price']",
                "[class*='Price']",
                "[data-testid*='price']",
                ".price", ".listing-price", "[data-price]",
                ".property-price", ".cost", ".amount",
            ]
            
            for selector in price_selectors:
                try:
                    price_elems = element.find_elements(By.CSS_SELECTOR, selector)
                    for price_elem in price_elems:
                        price_text = price_elem.text.strip()
                        if price_text and '$' in price_text:
                            # Extract just the price part (stop at non-digit after comma)
                            # Handle format: "$665,000" or "$665,0004" (with beds number)
                            price_match = re.search(r'\$[\d,]+', price_text)
                            if price_match:
                                price_str = price_match.group(0)
                                # If price is followed by digits (beds number), remove them
                                # Check if next char after match is a digit (part of beds)
                                match_end = price_match.end()
                                if match_end < len(price_text):
                                    next_char = price_text[match_end:match_end+5]
                                    # If next is digit+space+letter (like "4 Beds"), price is correct
                                    # If next is just digit (like "4"), it might be part of price
                                    if re.match(r'^\d+[A-Za-z]', next_char):
                                        # Price ends correctly, but might have trailing digit
                                        # Check if price_str ends with digit that's actually beds
                                        if len(price_str) > 8 and price_str[-1].isdigit():
                                            # Might be "$665,0004" - remove last digit
                                            price_str = price_str[:-1]
                                listing_data['price'] = price_str
                                break
                    if listing_data['price']:
                        break
                except:
                    continue
            
            # Try XPath for price (contains $) - more specific
            if not listing_data['price']:
                try:
                    # Look for elements containing $ with numbers (short text = price)
                    price_elems = element.find_elements(By.XPATH, ".//*[contains(text(), '$') and string-length(text()) < 20]")
                    for price_elem in price_elems:
                        price_text = price_elem.text.strip()
                        # Extract price pattern: $665,000 (stop before any non-digit/non-comma)
                        price_match = re.search(r'\$[\d,]+', price_text)
                        if price_match:
                            listing_data['price'] = price_match.group(0)
                            break
                except:
                    pass
            
            # If price not found, search in element text using regex - FIXED PATTERNS
            if not listing_data['price']:
                # Card text format: "$665,0004 Beds" - need to stop at word boundary
                # Pattern: $ followed by digits/commas, stop before letter or space+letter
                price_patterns = [
                    r'\$[\d,]+(?=\s*[A-Za-z]|\s+\d|\s*$)',  # $665,000 before "4 Beds" or end
                    r'\$[\d,]+',  # Fallback: $665,000 or $665000
                    r'\$\d{1,3}(?:,\d{3})*(?:\.\d+)?',  # $665,000 format
                ]
                for pattern in price_patterns:
                    match = re.search(pattern, element_text)
                    if match:
                        price_str = match.group(0)
                        # Clean and format: remove any trailing digits that might be from "Beds"
                        # If price ends with digits followed by space+letter, it's wrong
                        if re.search(r'\d\s+[A-Za-z]', price_str):
                            continue
                        # Format the price properly
                        clean_price = price_str.replace('$', '').replace(',', '').strip()
                        # Remove any trailing digits that are actually part of next field
                        if clean_price and clean_price.isdigit():
                            # Check if last few digits are actually beds (if followed by "Beds" or "Baths")
                            listing_data['price'] = f"${int(clean_price):,}"
                            break
            
            # Extract beds - FIXED for website format: "$665,0004 Beds" (no space before number)
            # Card text format: "4557 South Calumet AvenueChicago, IL 60653$665,0004 Beds4 Baths"
            # Try specific selectors first: <span class="px-2">4 Beds</span>
            beds_selectors = [
                "span[class*='px-2']",  # Exact: "px-2" class
                "span[class*='px']",  # Contains "px"
                "div[class*='text-sm'] span",  # In text-sm div
            ]
            
            for selector in beds_selectors:
                try:
                    beds_elems = element.find_elements(By.CSS_SELECTOR, selector)
                    for beds_elem in beds_elems:
                        beds_text = beds_elem.text.strip()
                        if 'bed' in beds_text.lower() and not 'bath' in beds_text.lower():
                            # Extract number from "4 Beds"
                            beds_match = re.search(r'(\d+)\s*(?:bed|beds|br|bedroom|BR|Bed)', beds_text, re.IGNORECASE)
                            if beds_match:
                                beds_num = beds_match.group(1)
                                if beds_num and int(beds_num) <= 20:
                                    listing_data['beds'] = beds_num
                                    break
                    if listing_data['beds']:
                        break
                except:
                    continue
            
            # Fallback to regex on full text
            if not listing_data['beds']:
                beds_patterns = [
                    r'(?<!\d)(\d+)\s+(?:bed|beds|br|bedroom|BR|Bed)\b',  # "4 Beds" - negative lookbehind
                    r'(?<![,\d])(\d+)\s*(?:bed|beds)\b',  # Avoid matching from price
                    r'\b(\d+)\s+(?:bed|beds)',  # Word boundary + space
                    r'(\d+)\s*bed\b',  # "4 bed"
                    r'(\d+)\s*BR\b',  # "4 BR"
                ]
                
                for pattern in beds_patterns:
                    beds_match = re.search(pattern, element_text, re.IGNORECASE)
                    if beds_match:
                        beds_num = beds_match.group(1)
                        # Validate: beds should be reasonable (0-20), not part of price
                        if beds_num and int(beds_num) <= 20:
                            listing_data['beds'] = beds_num
                            break
            
            # Also try XPath for beds
            if not listing_data['beds']:
                try:
                    beds_elem = element.find_element(By.XPATH, ".//*[contains(text(), 'bed') or contains(text(), 'BR')]")
                    beds_text = beds_elem.text
                    beds_match = re.search(r'(\d+)', beds_text)
                    if beds_match:
                        listing_data['beds'] = beds_match.group(1)
                except:
                    pass
            
            # Extract baths - FIXED for website format: "4 Beds4 Baths" (no space before number)
            # Try specific selectors first: <span class="border-l border-white pl-2">4 Baths</span>
            baths_selectors = [
                "span[class*='border-l']",  # Has border-l class
                "span[class*='pl-2']",  # Has pl-2 class
                "div[class*='text-sm'] span:last-child",  # Last span in text-sm div
            ]
            
            for selector in baths_selectors:
                try:
                    baths_elems = element.find_elements(By.CSS_SELECTOR, selector)
                    for baths_elem in baths_elems:
                        baths_text = baths_elem.text.strip()
                        if 'bath' in baths_text.lower() and not 'bed' in baths_text.lower():
                            # Extract number from "4 Baths" or "2.5 Baths"
                            baths_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|baths|ba|bathroom|BA|Bath)', baths_text, re.IGNORECASE)
                            if baths_match:
                                baths_num = baths_match.group(1)
                                if baths_num:
                                    try:
                                        if float(baths_num) <= 30:
                                            listing_data['baths'] = baths_num
                                            break
                                    except:
                                        pass
                    if listing_data['baths']:
                        break
                except:
                    continue
            
            # Fallback to regex on full text
            if not listing_data['baths']:
                baths_patterns = [
                    r'(?<!\d)(\d+(?:\.\d+)?)\s+(?:bath|baths|ba|bathroom|BA|Bath)\b',  # "4 Baths" - avoid price digits
                    r'(?<![,\d])(\d+(?:\.\d+)?)\s*(?:bath|baths)\b',  # Avoid matching from price
                    r'\b(\d+(?:\.\d+)?)\s+(?:bath|baths)',  # Word boundary + space
                    r'(\d+(?:\.\d+)?)\s*bath\b',  # "4 bath"
                    r'(\d+(?:\.\d+)?)\s*BA\b',  # "4 BA"
                ]
                
                for pattern in baths_patterns:
                    baths_match = re.search(pattern, element_text, re.IGNORECASE)
                    if baths_match:
                        baths_num = baths_match.group(1)
                        # Validate: baths should be reasonable (0-30), not part of price
                        if baths_num:
                            try:
                                if float(baths_num) <= 30:
                                    listing_data['baths'] = baths_num
                                    break
                            except:
                                pass
            
            # Also try XPath for baths
            if not listing_data['baths']:
                try:
                    baths_elem = element.find_element(By.XPATH, ".//*[contains(text(), 'bath') or contains(text(), 'BA')]")
                    baths_text = baths_elem.text
                    baths_match = re.search(r'(\d+(?:\.\d+)?)', baths_text)
                    if baths_match:
                        listing_data['baths'] = baths_match.group(1)
                except:
                    pass
            
            # Extract square feet - FIXED for website format
            # Card text format: "2048 SqFt" or "2,048 SqFt" - might be after baths
            sqft_patterns = [
                r'(?<!\d)([\d,]+)\s+(?:sq|square)\s*(?:ft|feet|FT|SF|sqft|sq\.ft\.)\b',  # "2048 SqFt" - avoid price digits
                r'(?<![,\d])([\d,]+)\s*(?:sq|square)\s*(?:ft|feet)\b',  # Avoid matching from price
                r'\b([\d,]+)\s+(?:sq|square)\s*(?:ft|feet)',  # Word boundary + space
                r'([\d,]+)\s*sqft\b',  # "2048 sqft"
                r'([\d,]+)\s*SF\b',  # "2048 SF"
                r'([\d,]+)\s*sq\.?\s*ft\.?\b',  # "2048 sq.ft."
            ]
            
            for pattern in sqft_patterns:
                sqft_match = re.search(pattern, element_text, re.IGNORECASE)
                if sqft_match:
                    sqft_num = sqft_match.group(1).replace(',', '')
                    # Validate: sqft should be reasonable (100-50000), not part of price
                    if sqft_num and sqft_num.isdigit():
                        sqft_int = int(sqft_num)
                        if 100 <= sqft_int <= 50000:
                            listing_data['square_feet'] = sqft_num
                            break
            
            # Try specific CSS selectors for square feet (from search results page)
            if not listing_data['square_feet']:
                sqft_selectors = [
                    "span[class*='border-l'][class*='px-3']",  # Common: "border-l border-gray-light px-3"
                    "span[class*='border-gray-light']",  # Contains border-gray-light
                    "div[class*='text-center'] span",  # In text-center div
                    "div[class*='flex'][class*='items-center'] span",  # In flex container
                ]
                
                for selector in sqft_selectors:
                    try:
                        sqft_elems = element.find_elements(By.CSS_SELECTOR, selector)
                        for sqft_elem in sqft_elems:
                            sqft_text = sqft_elem.text.strip()
                            if 'sqft' in sqft_text.lower() or 'square' in sqft_text.lower():
                                # Extract number from "2048 SqFt"
                                sqft_match = re.search(r'(\d{1,3}(?:,\d{3})*)', sqft_text)
                                if sqft_match:
                                    sqft_num = sqft_match.group(1).replace(',', '')
                                    if sqft_num.isdigit():
                                        sqft_int = int(sqft_num)
                                        if 100 <= sqft_int <= 50000:
                                            listing_data['square_feet'] = sqft_num
                                            break
                        if listing_data['square_feet']:
                            break
                    except:
                        continue
            
            # Also try XPath for square feet
            if not listing_data['square_feet']:
                try:
                    sqft_elem = element.find_element(By.XPATH, ".//*[contains(text(), 'sq') or contains(text(), 'SF')]")
                    sqft_text = sqft_elem.text
                    sqft_match = re.search(r'([\d,]+)', sqft_text)
                    if sqft_match:
                        listing_data['square_feet'] = sqft_match.group(1).replace(',', '')
                except:
                    pass
            
            # Fallback to original method
            if not listing_data['square_feet']:
                sqft = self.extract_square_feet(element_text)
                if sqft:
                    listing_data['square_feet'] = sqft
            
            # Extract time of post
            time_selectors = [
                ".date", ".posted", ".time", "[data-date]",
                ".listing-date", ".post-date"
            ]
            
            for selector in time_selectors:
                try:
                    time_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if time_elem:
                        listing_data['time_of_post'] = time_elem.text.strip()
                        break
                except:
                    continue
            
            # If not found, search for date patterns
            if not listing_data['time_of_post']:
                date_patterns = [
                    r'(?:posted|listed|added)\s*:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                    r'(\d+\s+(?:day|days|week|weeks|month|months)\s+ago)',
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, element_text, re.IGNORECASE)
                    if date_match:
                        listing_data['time_of_post'] = date_match.group(1) if len(date_match.groups()) > 0 else date_match.group(0)
                        break
            
            # CHECK FOR MISSING DATA - Always visit listing page if ANY critical data is missing
            # This ensures we get complete data for all listings
            missing_critical = []
            
            # Check for price - also check if it's "Price on Request" or similar
            price_value = listing_data.get('price', '')
            if not listing_data['price'] or listing_data['price'] == 'null' or listing_data['price'] == 'None':
                missing_critical.append('price')
            elif isinstance(price_value, str) and ('request' in price_value.lower() or 'contact' in price_value.lower() or 'call' in price_value.lower()):
                # If price is "Price on Request" or similar, mark as missing to fetch actual price
                missing_critical.append('price')
                logger.debug(f"Found 'Price on Request' text, will fetch actual price from listing page")
            
            if not listing_data['beds'] or listing_data['beds'] == 'null' or listing_data['beds'] == 'None':
                missing_critical.append('beds')
            
            if not listing_data['baths'] or listing_data['baths'] == 'null' or listing_data['baths'] == 'None':
                missing_critical.append('baths')
            
            if not listing_data['square_feet'] or listing_data['square_feet'] == 'null' or listing_data['square_feet'] == 'None':
                missing_critical.append('square_feet')
            
            # ALWAYS visit listing page if we have a link AND any critical data is missing
            # IMPORTANT: Always visit individual page if ANY data is missing to get complete information
            # This ensures we get actual values instead of "Price on Request" or "N/A"
            should_visit_page = listing_data['listing_link'] and len(missing_critical) > 0
                
            # Also visit if we have partial data but want to ensure completeness
            # Some listings show data on search page but complete data is on individual page
            if not should_visit_page and listing_data['listing_link']:
                # Even if we have some data, visit page to get missing fields (especially sqft)
                if not listing_data['square_feet']:
                    should_visit_page = True
                    missing_critical = ['square_feet']  # Add sqft to missing list
            
            # FORCE visit if price is "Price on Request" or similar placeholder
            if listing_data['listing_link'] and listing_data.get('price'):
                price_str = str(listing_data['price']).lower()
                if any(word in price_str for word in ['request', 'contact', 'call', 'inquiry', 'ask']):
                    should_visit_page = True
                    if 'price' not in missing_critical:
                        missing_critical.append('price')
                    logger.debug(f"Price placeholder detected, will fetch actual price from listing page")
            
            if should_visit_page:
                logger.info(f"Missing critical fields {missing_critical} for listing, fetching from detail page...")
                try:
                    # Save current URL to return to
                    current_url = self.driver.current_url
                    
                    # Fetch details from individual listing page (with timeout)
                    page_details = self.fetch_listing_details(listing_data['listing_link'])
                    
                    # Fill in missing data - ensure we get all available data
                    # Also update existing data if individual page has more accurate/complete data
                    if page_details['price']:
                        if not listing_data['price'] or listing_data['price'] == 'null':
                            listing_data['price'] = page_details['price']
                            logger.debug(f"✓ Fetched price: {page_details['price']}")
                        elif listing_data['price'] == 'Price on Request' or 'Request' in str(listing_data['price']):
                            # Replace "Price on Request" with actual price if found
                            listing_data['price'] = page_details['price']
                            logger.info(f"✓ Replaced 'Price on Request' with actual price: {page_details['price']}")
                    
                    if page_details['beds']:
                        if not listing_data['beds'] or listing_data['beds'] == 'null':
                            listing_data['beds'] = page_details['beds']
                            logger.debug(f"✓ Fetched beds: {page_details['beds']}")
                    
                    if page_details['baths']:
                        if not listing_data['baths'] or listing_data['baths'] == 'null':
                            listing_data['baths'] = page_details['baths']
                            logger.debug(f"✓ Fetched baths: {page_details['baths']}")
                    
                    if page_details['square_feet']:
                        if not listing_data['square_feet'] or listing_data['square_feet'] == 'null':
                            listing_data['square_feet'] = page_details['square_feet']
                            logger.debug(f"✓ Fetched sqft: {page_details['square_feet']}")
                    
                    if page_details['time_of_post']:
                        if not listing_data['time_of_post'] or listing_data['time_of_post'] == 'null':
                            listing_data['time_of_post'] = page_details['time_of_post']
                    
                    # Return to search results page
                    self.driver.get(current_url)
                    time.sleep(1)  # Reduced wait time
                    
                    fetched = [f for f in missing_critical if listing_data.get(f)]
                    if fetched:
                        logger.info(f"✓ Successfully fetched: {fetched}")
                    else:
                        logger.warning(f"⚠️ Could not fetch any data from listing page for: {missing_critical}")
                except Exception as e:
                    logger.warning(f"Could not fetch details from listing page: {e}")
                    # Try to return to search page even if error
                    try:
                        self.driver.get(current_url)
                        time.sleep(1)
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"Error parsing listing element: {e}")
        
        return listing_data
    
    def save_to_json(self, data: List[Dict], filename: str = 'forsalebyowner_listings.json'):
        """Save scraped data to JSON file. Overwrites existing file with fresh data."""
        # 'w' mode overwrites existing file - ensures NEW data each run
        import os
        from datetime import datetime
        
        # Post-processing: Clean null values and ensure data quality
        cleaned_data = []
        null_count = 0
        for listing in data:
            cleaned_listing = {}
            for key, value in listing.items():
                # Convert null/None to None (JSON null)
                if value is None or value == 'null' or value == 'None' or value == '':
                    cleaned_listing[key] = None
                    if key in ['price', 'beds', 'baths', 'square_feet']:
                        null_count += 1
                else:
                    cleaned_listing[key] = value
            cleaned_data.append(cleaned_listing)
        
        if null_count > 0:
            logger.warning(f"⚠️ Found {null_count} null values in critical fields. Consider re-running scraper for complete data.")
        
        # Check if file exists (old data)
        if os.path.exists(filename):
            old_size = os.path.getsize(filename)
            logger.info(f"Overwriting existing {filename} (old size: {old_size} bytes)")
        
        with open(filename, 'w', encoding='utf-8') as f:
            # Add metadata to JSON
            output_data = {
                'scrape_timestamp': datetime.now().isoformat(),
                'total_listings': len(cleaned_data),
                'listings': cleaned_data
            }
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        new_size = os.path.getsize(filename)
        logger.info(f"NEW data saved to {filename} ({len(cleaned_data)} listings, {new_size} bytes) - Previous data overwritten")
        
        # Log data completeness
        with_prices = sum(1 for l in cleaned_data if l.get('price'))
        with_beds = sum(1 for l in cleaned_data if l.get('beds'))
        with_baths = sum(1 for l in cleaned_data if l.get('baths'))
        with_sqft = sum(1 for l in cleaned_data if l.get('square_feet'))
        logger.info(f"📊 Data Completeness: Prices: {with_prices}/{len(cleaned_data)}, Beds: {with_beds}/{len(cleaned_data)}, Baths: {with_baths}/{len(cleaned_data)}, SqFt: {with_sqft}/{len(cleaned_data)}")
    
    def save_to_csv(self, data: List[Dict], filename: str = 'forsalebyowner_listings.csv'):
        """Save scraped data to CSV file with clear, descriptive headers. Overwrites existing file."""
        if not data:
            logger.warning("No data to save")
            return
        
        # More descriptive field names for clarity
        fieldnames = [
            'Property_Address', 
            'Listing_Price', 
            'Number_of_Bedrooms', 
            'Number_of_Bathrooms', 
            'Square_Feet', 
            'Listing_URL', 
            'Date_Posted'
        ]
        
        # Mapping from internal keys to descriptive headers
        field_mapping = {
            'address': 'Property_Address',
            'price': 'Listing_Price',
            'beds': 'Number_of_Bedrooms',
            'baths': 'Number_of_Bathrooms',
            'square_feet': 'Square_Feet',
            'listing_link': 'Listing_URL',
            'time_of_post': 'Date_Posted'
        }
        
        # 'w' mode overwrites existing file - ensures fresh NEW data each run
        import os
        from datetime import datetime
        
        # Check if file exists (old data)
        if os.path.exists(filename):
            old_size = os.path.getsize(filename)
            old_count = sum(1 for line in open(filename)) - 1  # Subtract header
            logger.info(f"Overwriting existing {filename} (old: {old_count} listings, {old_size} bytes)")
        
        # ALWAYS overwrite with fresh data - 'w' mode ensures complete replacement
        from datetime import datetime
        update_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            # ALWAYS write header row first - ensures clear column titles
            writer.writeheader()
            
            # Write data rows with proper mapping
            for idx, item in enumerate(data, 1):
                # Map internal keys to descriptive headers for clarity
                row = {}
                for old_key, new_key in field_mapping.items():
                    value = item.get(old_key, '')
                    # Clean up None values
                    if value is None:
                        value = ''
                    row[new_key] = value
                writer.writerow(row)
        
        new_size = os.path.getsize(filename)
        update_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"CSV FILE UPDATED: {filename}")
        logger.info(f"  - Update Time: {update_timestamp}")
        logger.info(f"  - Headers: {', '.join(fieldnames)}")
        logger.info(f"  - Total listings: {len(data)}")
        logger.info(f"  - File size: {new_size} bytes")
        logger.info(f"  - Status: Previous data overwritten with FRESH data")
    
    def compare_with_previous_data(self, new_listings: List[Dict]) -> Dict:
        """
        Compare new data with previous data to detect changes.
        
        Returns:
            Dictionary with comparison results
        """
        import os
        import json
        from datetime import datetime
        
        result = {
            'previous_exists': False,
            'previous_count': 0,
            'new_count': len(new_listings),
            'new_listings': [],
            'removed_listings': [],
            'same_listings': [],
            'timestamp': datetime.now().isoformat()
        }
        
        json_file = 'forsalebyowner_listings.json'
        
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                    
                # Handle both old format (list) and new format (with metadata)
                if isinstance(old_data, dict) and 'listings' in old_data:
                    old_listings = old_data['listings']
                    old_timestamp = old_data.get('scrape_timestamp', 'Unknown')
                else:
                    old_listings = old_data
                    old_timestamp = 'Unknown'
                
                result['previous_exists'] = True
                result['previous_count'] = len(old_listings)
                result['previous_timestamp'] = old_timestamp
                
                # Create sets of listing URLs for comparison
                old_urls = {listing.get('listing_link', '') for listing in old_listings if listing.get('listing_link')}
                new_urls = {listing.get('listing_link', '') for listing in new_listings if listing.get('listing_link')}
                
                # Find new listings (in new but not in old)
                result['new_listings'] = [url for url in new_urls if url not in old_urls]
                
                # Find removed listings (in old but not in new)
                result['removed_listings'] = [url for url in old_urls if url not in new_urls]
                
                # Find same listings (in both)
                result['same_listings'] = [url for url in new_urls if url in old_urls]
                
            except Exception as e:
                logger.error(f"Error comparing with previous data: {e}")
        
        return result
    
    def print_data_comparison(self, comparison: Dict):
        """Print comparison results to show data differences."""
        print("\n" + "=" * 60)
        print("DATA COMPARISON (New vs Previous Run)")
        print("=" * 60)
        
        if not comparison['previous_exists']:
            print("\n[FIRST RUN] No previous data found.")
            print(f"  - This is the first time scraping")
            print(f"  - Saved {comparison['new_count']} listings")
        else:
            print(f"\nPrevious Run:")
            print(f"  - Timestamp: {comparison.get('previous_timestamp', 'Unknown')}")
            print(f"  - Listings: {comparison['previous_count']}")
            
            print(f"\nCurrent Run:")
            print(f"  - Timestamp: {comparison['timestamp']}")
            print(f"  - Listings: {comparison['new_count']}")
            
            print(f"\nChanges Detected:")
            
            if comparison['new_count'] != comparison['previous_count']:
                diff = comparison['new_count'] - comparison['previous_count']
                if diff > 0:
                    print(f"  [NEW] Count increased by {diff} listings")
                else:
                    print(f"  [REMOVED] Count decreased by {abs(diff)} listings")
            else:
                print(f"  [SAME] Same number of listings ({comparison['new_count']})")
            
            if comparison['new_listings']:
                print(f"\n  [NEW LISTINGS] Found {len(comparison['new_listings'])} new listings:")
                for i, url in enumerate(comparison['new_listings'][:5], 1):  # Show first 5
                    address = url.split('/listing/')[1].split('/')[0].replace('-', ' ').title() if '/listing/' in url else url
                    print(f"    {i}. {address}")
                if len(comparison['new_listings']) > 5:
                    print(f"    ... and {len(comparison['new_listings']) - 5} more")
            
            if comparison['removed_listings']:
                print(f"\n  [REMOVED] {len(comparison['removed_listings'])} listings removed from previous run")
            
            if comparison['same_listings']:
                print(f"\n  [UNCHANGED] {len(comparison['same_listings'])} listings are same as previous run")
            
            # Summary
            if comparison['new_listings'] or comparison['removed_listings']:
                print(f"\n  [RESULT] DATA IS DIFFERENT - Website has updated!")
            else:
                print(f"\n  [RESULT] DATA IS SAME - No changes detected on website")
        
        print("=" * 60)
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


def main():
    """Main function to run the scraper."""
    url = "https://www.forsalebyowner.com/search/list/chicago-illinois"
    
    print("=" * 60)
    print("ForSaleByOwner.com Scraper (Selenium Version)")
    print("=" * 60)
    print(f"Target URL: {url}")
    print(f"Extracting: address, price, beds, baths, square feet, listing link, time of post")
    print("=" * 60)
    print()
    
    scraper = None
    try:
        # Initialize scraper (headless=False to see browser, headless=True to run in background)
        # Enable real-time storage to Supabase as we scrape
        api_url = os.getenv('API_URL', 'http://localhost:3000/api/listings/add')
        scraper = ForSaleByOwnerSeleniumScraper(base_url=url, headless=True, delay=2.0, api_url=api_url)
        
        # FORCE FULL SCRAPE to get all listings from website
        # Always scrape all listings to ensure we get complete data for sync
        # Note: With real-time storage enabled, listings are stored in Supabase as we scrape
        skip_existing = False  # Always do full scrape to get all listings from website
        
        print("\n[FULL SCRAPE MODE] Scraping ALL listings from website...")
        print("This ensures we get complete data for sync with database.")
        
        # Scrape listings (always full scrape - sync logic will handle add/update/delete)
        print("Starting to scrape...")
        all_listings = scraper.scrape_listings(skip_existing=skip_existing)
        
        if not all_listings:
            print("\nWARNING: No listings found!")
            print("This might be because:")
            print("1. The website structure has changed")
            print("2. The website requires additional authentication")
            print("3. The website is blocking automated requests")
            print("\nCheck debug_page_source.html for the actual HTML structure.")
            return
        
        # Save results
        print(f"\nSUCCESS: Scraped {len(all_listings)} listings from website!")
        print(f"Expected: 132 listings")
        if len(all_listings) < 132:
            print(f"⚠️  WARNING: Only got {len(all_listings)} listings, expected 132")
        else:
            print(f"✅ Got all {len(all_listings)} listings!")
        
        # Compare with previous data to show changes
        comparison_result = scraper.compare_with_previous_data(all_listings)
        scraper.print_data_comparison(comparison_result)
        
        # Save all listings (existing + new)
        scraper.save_to_json(all_listings, 'forsalebyowner_listings.json')
        scraper.save_to_csv(all_listings, 'forsalebyowner_listings.csv')
        
        # Display sample
        print("\n" + "=" * 60)
        print("Sample of extracted data:")
        print("=" * 60)
        if all_listings:
            sample = all_listings[0]
            # Display with clear labels
            field_labels = {
                'address': 'Property Address',
                'price': 'Listing Price',
                'beds': 'Number of Bedrooms',
                'baths': 'Number of Bathrooms',
                'square_feet': 'Square Feet',
                'listing_link': 'Listing URL',
                'time_of_post': 'Date Posted'
            }
            
            for key, value in sample.items():
                label = field_labels.get(key, key.replace('_', ' ').title())
                display_value = value if value else 'Not Available'
                print(f"{label:25}: {display_value}")
        
        print("\nSUCCESS: Scraping complete!")
        print(f"\nFiles Updated (Previous data overwritten):")
        print(f"   - forsalebyowner_listings.json")
        print(f"   - forsalebyowner_listings.csv")
        
        print(f"\n" + "=" * 60)
        print("CSV FILE DETAILS:")
        print("=" * 60)
        print(f"Status: UPDATED - Fresh data saved")
        print(f"Location: forsalebyowner_listings.csv")
        print(f"Total Listings: {len(all_listings)}")
        print(f"\nColumn Headers (First Row):")
        print(f"   1. Property_Address - Property ka full address")
        print(f"   2. Listing_Price - Property ki price")
        print(f"   3. Number_of_Bedrooms - Kitne bedrooms")
        print(f"   4. Number_of_Bathrooms - Kitne bathrooms")
        print(f"   5. Square_Feet - Property ka size")
        print(f"   6. Listing_URL - Property ka direct link")
        print(f"   7. Date_Posted - Listing kab post hui")
        print(f"\nNote: CSV file har run par automatically UPDATE hoti hai")
        print(f"      Headers hamesha first row mein hote hain")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print("\nERROR: Failed to scrape. Check the logs above for details.")
        print("\nMake sure you have:")
        print("1. Chrome browser installed")
        print("2. ChromeDriver installed and in PATH")
        print("3. selenium package installed: pip install selenium")
        
    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    main()


