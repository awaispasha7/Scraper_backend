"""
Location Search Utilities
Searches platforms to get the actual listing URL from a location name
Hybrid approach: Uses Selenium first, falls back to Playwright with Browserless.io if bot detection occurs
"""

import re
import time
import random
from typing import Optional
import logging
import os
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
        
        # Use headful mode (not headless) - many sites detect headless browsers
        # Note: In cloud environments, you won't see the GUI, but it helps bypass detection
        chrome_options.add_argument('--headless=new')  # Can try headless=new for better compatibility
        
        # Standard options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Enhanced bot evasion - remove automation signals
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Use a realistic, recent user agent
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Additional stealth options
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--disable-site-isolation-trials')
        chrome_options.add_argument('--lang=en-US,en')
        chrome_options.add_argument('--accept-lang=en-US,en')
        
        # Preferences to make browser look more human
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
            },
            "profile.managed_default_content_settings": {
                "images": 1  # Allow images (some sites check for this)
            },
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Note: Browserless.io V2+ does NOT support Selenium WebDriver
        # They only support Puppeteer/Playwright via WebSocket
        # If you want to use Browserless.io, you'd need to switch to Playwright
        # For now, we'll use local Chrome with enhanced bot evasion
        
        browserless_token = os.getenv("BROWSERLESS_TOKEN")
        if browserless_token:
            print("[LocationSearcher] WARNING: BROWSERLESS_TOKEN is set, but Browserless.io V2+ does not support Selenium WebDriver")
            print("[LocationSearcher] Browserless.io only supports Puppeteer/Playwright. Falling back to local Chrome.")
            print("[LocationSearcher] To use Browserless.io, you would need to migrate to Playwright.")
            print("[LocationSearcher] See: https://docs.browserless.io/overview/connection-urls")
        
        try:
            # Always use local Chrome/Chromium with enhanced bot evasion
            print("[LocationSearcher] Using local Chrome/Chromium with enhanced bot evasion")
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
            
            # Execute script to remove webdriver property (anti-detection)
            try:
                driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                    'source': '''
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    '''
                })
            except Exception as e:
                logger.warning(f"Could not execute CDP command: {e}")
            
            return driver
        except Exception as e:
            logger.error(f"[LocationSearcher] Failed to initialize WebDriver: {e}")
            raise Exception(f"Could not initialize browser: {str(e)}. Please ensure Chrome/Chromium is installed.")
    
    @classmethod
    def _search_trulia_with_playwright(cls, location: str) -> Optional[str]:
        """
        Search Trulia using Playwright with Browserless.io (fallback when bot detected)
        """
        try:
            from playwright.sync_api import sync_playwright
            
            browserless_token = os.getenv("BROWSERLESS_TOKEN")
            if not browserless_token:
                print("[LocationSearcher] No BROWSERLESS_TOKEN - cannot use Playwright fallback")
                return None
            
            
            browserless_token = browserless_token.strip()
            location_clean = location.strip()
            print(f"[LocationSearcher] Trying Playwright with Browserless.io for: {location_clean}")
            
            # Get region (default: sfo)
            region = os.getenv("BROWSERLESS_REGION", "sfo").lower()
            if region not in ["sfo", "lon", "ams"]:
                region = "sfo"
            
            # Browserless.io WebSocket endpoint for CDP connection with stealth mode
            # Add stealth=true parameter for better bot evasion
            browserless_url = f"wss://production-{region}.browserless.io?token={browserless_token}&stealth=true"
            
            with sync_playwright() as p:
                print(f"[LocationSearcher] Connecting to Browserless.io via Playwright CDP...")
                print(f"[LocationSearcher] Endpoint: wss://production-{region}.browserless.io (region: {region}, stealth: true)")
                
                try:
                    # Connect to Browserless.io via CDP
                    browser = p.chromium.connect_over_cdp(browserless_url)
                    print(f"[LocationSearcher] Successfully connected to Browserless.io")
                    
                    # Always create a fresh context with stealth settings
                    # Don't reuse existing contexts as they may be flagged
                    print(f"[LocationSearcher] Creating fresh browser context with stealth settings...")
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        viewport={"width": 1920, "height": 1080},
                        locale="en-US",
                        timezone_id="America/New_York",
                        permissions=["geolocation"],
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept-Encoding": "gzip, deflate, br",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "none",
                            "Upgrade-Insecure-Requests": "1",
                        }
                    )
                    
                    # Add stealth scripts to hide automation
                    context.add_init_script("""
                        // Override the `plugins` property to use a custom getter
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        
                        // Override the `languages` property
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en']
                        });
                        
                        // Remove webdriver property
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        
                        // Mock chrome property
                        window.chrome = {
                            runtime: {}
                        };
                        
                        // Override permissions
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                    """)
                    
                    page = context.new_page()
                    print(f"[LocationSearcher] Created new page with stealth configuration")
                    
                except Exception as connect_error:
                    print(f"[LocationSearcher] Failed to connect to Browserless.io: {connect_error}")
                    import traceback
                    print(f"[LocationSearcher] Connection traceback: {traceback.format_exc()}")
                    return None
                
                # Navigate to Trulia (skip warm-up, go directly)
                print(f"[LocationSearcher] Navigating to Trulia...")
                logger.info("[STATUS] Bypassing bot detection and CAPTCHAs... This may take 30-60 seconds")
                print(f"[LocationSearcher] [STATUS] Bypassing bot detection and CAPTCHAs... This may take 30-60 seconds")
                
                try:
                    page.goto("https://www.trulia.com", wait_until="domcontentloaded", timeout=60000)  # Increased to 60 seconds
                    time.sleep(2)  # Just enough to let initial page load
                except Exception as goto_error:
                    if "timeout" in str(goto_error).lower():
                        logger.warning("[STATUS] Page load timeout - Trulia may be blocking. Retrying with longer timeout...")
                        print(f"[LocationSearcher] [STATUS] Page load timeout - retrying with longer timeout...")
                        # Retry with networkidle instead of domcontentloaded
                        try:
                            page.goto("https://www.trulia.com", wait_until="networkidle", timeout=90000)  # 90 seconds
                            time.sleep(2)
                        except Exception as retry_error:
                            logger.error(f"Failed to load Trulia after retry: {retry_error}")
                            print(f"[LocationSearcher] Failed to load Trulia after retry: {retry_error}")
                            raise
                    else:
                        raise
                
                page_title = page.title()
                current_url = page.url
                print(f"[LocationSearcher] Page title: {page_title}, URL: {current_url}")
                
                # PRIORITY: Check if search box exists FIRST (best indicator of success)
                # PerimeterX code may be present even when page works - don't rely on it alone
                print(f"[LocationSearcher] Checking for search box (waiting up to 10 seconds)...")
                logger.info("[STATUS] Waiting for page to fully load and checking for bot detection...")
                print(f"[LocationSearcher] [STATUS] Waiting for page to fully load and checking for bot detection...")
                search_box_check = None
                
                for wait_attempt in range(5):  # Try 5 times with 2 second delays
                    selectors_to_check = [
                        "input[data-testid='location-search-input']",
                        "input#banner-search",
                        "input[aria-label*='Search for City']",
                        "input.react-autosuggest__input",
                    ]
                    
                    for selector in selectors_to_check:
                        try:
                            search_box_check = page.query_selector(selector)
                            if search_box_check:
                                try:
                                    if search_box_check.is_visible():
                                        print(f"[LocationSearcher] ✓ Search box found and visible: {selector}")
                                        break
                                except:
                                    # If visibility check fails, try to use it anyway
                                    print(f"[LocationSearcher] ✓ Search box found (visibility uncertain): {selector}")
                                    break
                        except:
                            continue
                    
                    if search_box_check:
                        break
                    
                    if wait_attempt < 4:
                        print(f"[LocationSearcher] Search box not found yet, waiting 2 more seconds... (attempt {wait_attempt + 2}/5)")
                        time.sleep(2)
                
                if not search_box_check:
                    # Search box not found - check for explicit blocking messages
                    print(f"[LocationSearcher] Search box not found. Checking for blocking messages...")
                    page_content = page.content().lower()
                    
                    # Only check for EXPLICIT blocking messages, not just PerimeterX presence
                    explicit_blocking = (
                        "access to this page has been denied" in page_content or
                        "please verify you are human" in page_content or
                        ("perimeterx" in page_content and ("sorry" in page_content or "blocked" in page_content and "access" in page_content))
                    )
                    
                    if explicit_blocking:
                        print(f"[LocationSearcher] Confirmed blocked. Trying alternative: Direct URL construction...")
                        # Last resort: Try constructing URL directly from location
                        constructed_url = cls._try_construct_trulia_url(location_clean)
                        if constructed_url:
                            try:
                                print(f"[LocationSearcher] Attempting constructed URL: {constructed_url}")
                                page.goto(constructed_url, wait_until="domcontentloaded", timeout=30000)
                                time.sleep(3)
                                final_url = page.url
                                if 'trulia.com' in final_url and final_url != 'https://www.trulia.com/':
                                    print(f"[LocationSearcher] ✓ Constructed URL worked: {final_url}")
                                    browser.close()
                                    return final_url
                            except Exception as e:
                                print(f"[LocationSearcher] Constructed URL failed: {e}")
                        
                        print(f"[LocationSearcher] All attempts failed. Trulia's bot detection is very aggressive.")
                        print(f"[LocationSearcher] Recommendation: Use a residential proxy or try again later.")
                        try:
                            browser.close()
                        except:
                            pass
                        return None
                    else:
                        # No explicit blocking but no search box - might be a loading issue
                        print(f"[LocationSearcher] Search box not found but no explicit blocking detected.")
                        print(f"[LocationSearcher] Page may still be loading JavaScript. Attempting to proceed...")
                        # Continue to try finding search box in next step
                
                print(f"[LocationSearcher] Proceeding with search...")
                
                # Find search box using Playwright
                search_box = None
                selectors_to_try = [
                    "input[data-testid='location-search-input']",
                    "input#banner-search",
                    "input[aria-label*='Search for City']",
                ]
                
                for selector in selectors_to_try:
                    try:
                        search_box = page.query_selector(selector)
                        if search_box and search_box.is_visible():
                            print(f"[LocationSearcher] Found search box with selector: {selector}")
                            break
                    except:
                        continue
                
                if not search_box:
                    print(f"[LocationSearcher] Could not find search box with Playwright")
                    browser.close()
                    return None
                
                # Fill search box directly (no slow typing needed - page is already loaded successfully)
                print(f"[LocationSearcher] Entering location '{location_clean}' into search box...")
                search_box.click()
                search_box.fill("")  # Clear
                search_box.fill(location_clean)  # Paste directly
                time.sleep(2)  # Wait for autocomplete suggestions to appear
                
                # Wait for suggestions and click the appropriate one
                try:
                    # Wait for suggestions container to appear
                    logger.info("[STATUS] Waiting for location suggestions...")
                    print(f"[LocationSearcher] [STATUS] Waiting for location suggestions...")
                    time.sleep(1)  # Give suggestions time to render
                    
                    # Try to find suggestions
                    suggestions = page.query_selector_all("#react-autowhatever-home-banner li, .react-autosuggest__suggestions-container li, ul[role='listbox'] li")
                    if suggestions:
                        visible_suggestions = []
                        for s in suggestions:
                            try:
                                if s.is_visible():
                                    suggestion_text = s.inner_text().strip()
                                    # Skip "Current Location" - we want actual location suggestions
                                    if suggestion_text and "current location" not in suggestion_text.lower():
                                        visible_suggestions.append((s, suggestion_text))
                            except:
                                continue
                        
                        if visible_suggestions:
                            # Use the first actual location suggestion (not "Current Location")
                            suggestion_element, suggestion_text = visible_suggestions[0]
                            print(f"[LocationSearcher] Clicking location suggestion: {suggestion_text[:80]}")
                            logger.info(f"[STATUS] Selecting location: {suggestion_text[:80]}")
                            
                            # Use JavaScript click to avoid connection issues
                            try:
                                suggestion_element.evaluate("element => element.click()")
                            except:
                                # Fallback to regular click
                                suggestion_element.click()
                            
                            # Wait for navigation
                            try:
                                page.wait_for_load_state("networkidle", timeout=10000)
                            except:
                                time.sleep(3)  # Fallback wait
                        else:
                            # No valid suggestions, try pressing Enter
                            print(f"[LocationSearcher] No valid suggestions found, pressing Enter")
                            search_box.press("Enter")
                            time.sleep(3)
                    else:
                        # No suggestions container, press Enter
                        print(f"[LocationSearcher] No suggestions container found, pressing Enter")
                        search_box.press("Enter")
                        time.sleep(3)
                except Exception as suggestion_error:
                    # If anything fails, try pressing Enter as fallback
                    print(f"[LocationSearcher] Error handling suggestions ({suggestion_error}), pressing Enter as fallback")
                    try:
                        search_box.press("Enter")
                        time.sleep(3)
                    except:
                        pass
                
                # Get final URL (wait for any navigation to complete)
                logger.info("[STATUS] Retrieving final URL...")
                print(f"[LocationSearcher] [STATUS] Retrieving final URL...")
                time.sleep(2)  # Give navigation time to complete
                
                try:
                    final_url = page.url
                    print(f"[LocationSearcher] Playwright final URL: {final_url}")
                except Exception as url_error:
                    print(f"[LocationSearcher] Error getting final URL: {url_error}")
                    final_url = None
                finally:
                    # Always close browser
                    try:
                        browser.close()
                    except:
                        pass
                
                if final_url and 'trulia.com' in final_url and final_url != 'https://www.trulia.com' and final_url != 'https://www.trulia.com/':
                    return final_url
                
                return None
                
        except ImportError:
            print("[LocationSearcher] Playwright not installed - cannot use Browserless.io fallback")
            print("[LocationSearcher] Install with: pip install playwright && playwright install chromium")
            return None
        except Exception as e:
            print(f"[LocationSearcher] Playwright fallback error: {e}")
            import traceback
            print(f"[LocationSearcher] Playwright traceback: {traceback.format_exc()}")
            return None
    
    @classmethod
    def search_trulia(cls, location: str) -> Optional[str]:
        """
        Search Trulia for a location using their search box.
        Skip Selenium (Trulia has heavy bot detection) - go straight to Playwright with Browserless.io.
        """
        location_clean = location.strip()
        logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
        
        # Skip Selenium for Trulia - it has heavy bot detection
        # Go straight to Playwright with Browserless.io
        print(f"[LocationSearcher] Trulia has heavy bot detection - skipping Selenium, using Playwright with Browserless.io directly")
        return cls._search_trulia_with_playwright(location_clean)
    
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
