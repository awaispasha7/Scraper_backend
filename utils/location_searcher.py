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
    def _try_construct_trulia_url(cls, location: str) -> Optional[str]:
        """
        Construct a Trulia URL directly from location string.
        Trulia URL patterns: /{STATE}/{City}/  (e.g., /MN/Minneapolis/)
        """
        try:
            location = location.strip()
            
            # Try to parse "City, State" format (e.g., "Minneapolis, MN")
            if ',' in location:
                parts = [p.strip() for p in location.split(',')]
                if len(parts) == 2:
                    city = parts[0].replace(' ', '_').replace('-', '_')
                    state = parts[1].upper().strip()
                    # Clean up state (remove extra spaces, take first 2 chars)
                    if len(state) > 2:
                        state = state[:2]
                    return f"https://www.trulia.com/{state}/{city}/"
            
            # Try to parse "City State" format (e.g., "Minneapolis MN")
            parts = location.split()
            if len(parts) >= 2:
                # Last part might be state abbreviation
                last_part = parts[-1].upper()
                if len(last_part) == 2 and last_part.isalpha():
                    # It's a state abbreviation
                    state = last_part
                    city = '_'.join(parts[:-1]).replace('-', '_')
                    return f"https://www.trulia.com/{state}/{city}/"
            
            # For single word (like "Minneapolis"), use common mappings or default to MN
            city = location.replace(' ', '_').replace('-', '_')
            
            # Common city-to-state mappings
            city_state_map = {
                'minneapolis': 'MN',
                'chicago': 'IL',
                'new_york': 'NY',
                'los_angeles': 'CA',
                'houston': 'TX',
                'phoenix': 'AZ',
                'philadelphia': 'PA',
                'san_antonio': 'TX',
                'san_diego': 'CA',
                'dallas': 'TX',
            }
            
            city_lower = city.lower()
            state = city_state_map.get(city_lower, 'MN')  # Default to MN if unknown
            
            return f"https://www.trulia.com/{state}/{city}/"
            
        except Exception as e:
            print(f"[LocationSearcher] Error constructing Trulia URL: {e}")
            return None
    
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
                
                # Fill search box and submit search
                print(f"[LocationSearcher] Entering location '{location_clean}' into search box...")
                logger.info(f"[STATUS] Searching for: {location_clean}")
                search_box.click()
                time.sleep(0.5)
                search_box.fill("")  # Clear
                search_box.fill(location_clean)  # Type the location
                time.sleep(2.5)  # Wait longer for autocomplete suggestions to appear
                
                # Get initial URL before submission
                initial_url = page.url
                print(f"[LocationSearcher] Initial URL: {initial_url}")
                
                # PRIORITY: Try clicking first autocomplete suggestion (like manual user behavior)
                search_submitted = False
                suggestion_clicked = False
                
                # Wait for suggestions to appear after typing
                print(f"[LocationSearcher] Looking for autocomplete suggestions...")
                logger.info("[STATUS] Waiting for location suggestions...")
                time.sleep(2)  # Give time for suggestions to appear
                
                # Try multiple selectors for Trulia autocomplete suggestions
                suggestion_selectors = [
                    "ul[role='listbox'] li",
                    "div[role='listbox'] div",
                    "ul[class*='autocomplete'] li",
                    "ul[class*='suggestion'] li",
                    "div[class*='suggestion']",
                    "li[class*='suggestion']",
                    "div[role='option']",
                    "[data-testid*='suggestion']",
                ]
                
                suggestion = None
                for selector in suggestion_selectors:
                    try:
                        # Check if page/browser is still alive
                        if page.is_closed():
                            print(f"[LocationSearcher] Page was closed, skipping suggestion search")
                            break
                        
                        suggestions = page.query_selector_all(selector)
                        if suggestions:
                            # Filter out non-location suggestions
                            for sug in suggestions:
                                try:
                                    if sug.is_visible():
                                        text = sug.inner_text().lower()
                                        # Skip generic suggestions
                                        if any(skip in text for skip in ['current location', 'search by commute', 'popular searches', 'suggested']):
                                            continue
                                        # If it contains our location or looks like a location
                                        if location_clean.lower() in text or ',' in text or any(word in text for word in ['minneapolis', 'city', 'mn', 'state']):
                                            suggestion = sug
                                            print(f"[LocationSearcher] Found suggestion: {text[:50]}")
                                            break
                                except Exception as sug_check_err:
                                    # Page might have closed, check and break if so
                                    if 'closed' in str(sug_check_err).lower() or 'target' in str(sug_check_err).lower():
                                        print(f"[LocationSearcher] Browser/page closed during suggestion check")
                                        break
                                    continue
                            if suggestion:
                                break
                    except Exception as selector_err:
                        # If page closed, break outer loop
                        if 'closed' in str(selector_err).lower() or 'target' in str(selector_err).lower():
                            print(f"[LocationSearcher] Browser/page closed during suggestion search")
                            break
                        continue
                
                if suggestion and not page.is_closed():
                    try:
                        print(f"[LocationSearcher] Clicking first autocomplete suggestion...")
                        suggestion.click()
                        suggestion_clicked = True
                        search_submitted = True
                        time.sleep(2)  # Wait for navigation after clicking suggestion
                        print(f"[LocationSearcher] Suggestion clicked, waiting for navigation...")
                    except Exception as click_err:
                        print(f"[LocationSearcher] Failed to click suggestion: {click_err}")
                        search_submitted = False
                
                # If no suggestion clicked and page is still alive, try other methods
                if not search_submitted and not page.is_closed():
                    print(f"[LocationSearcher] No suggestion clicked, trying other submission methods...")
                    logger.info("[STATUS] Submitting search...")
                    
                    # Method 1: Press Enter (most reliable when suggestions are shown)
                    try:
                        print(f"[LocationSearcher] Pressing Enter key...")
                        search_box.press("Enter")
                        search_submitted = True
                    except Exception as enter_err:
                        if 'closed' in str(enter_err).lower() or 'target' in str(enter_err).lower():
                            print(f"[LocationSearcher] Browser/page closed - cannot press Enter")
                        else:
                            print(f"[LocationSearcher] Enter key error: {enter_err}")
                    
                    # Method 2: Look for Trulia's search button
                    if not search_submitted and not page.is_closed():
                        try:
                            button_selectors = [
                                "button[type='submit']",
                                "button.SearchButton",
                                "button[aria-label*='Search']",
                                "form button[type='submit']",
                            ]
                            for selector in button_selectors:
                                try:
                                    if page.is_closed():
                                        break
                                    btn = page.query_selector(selector)
                                    if btn and btn.is_visible():
                                        print(f"[LocationSearcher] Found search button, clicking...")
                                        btn.click()
                                        search_submitted = True
                                        break
                                except:
                                    continue
                        except Exception as btn_err:
                            if 'closed' not in str(btn_err).lower():
                                print(f"[LocationSearcher] Button search error: {btn_err}")
                    
                    # Method 3: Try form submission
                    if not search_submitted and not page.is_closed():
                        try:
                            form = search_box.evaluate_handle("el => el.closest('form')")
                            if form:
                                print(f"[LocationSearcher] Submitting form directly...")
                                page.evaluate("form => form.submit()", form)
                                search_submitted = True
                        except Exception as form_err:
                            if 'closed' not in str(form_err).lower():
                                pass
                
                # Wait for navigation - but check if browser is still alive first
                final_url = None
                
                if page.is_closed():
                    print(f"[LocationSearcher] Page is closed - cannot wait for navigation")
                else:
                    print(f"[LocationSearcher] Waiting for navigation...")
                    logger.info("[STATUS] Waiting for page to redirect...")
                    
                    # Use fast polling to catch URL changes quickly (user says it happens within seconds)
                    print(f"[LocationSearcher] Polling URL frequently to catch navigation...")
                    max_wait_seconds = 10  # Reduced from 15 to fail faster
                    check_interval = 0.3  # Check every 300ms
                    max_checks = int(max_wait_seconds / check_interval)
                    
                    for check_attempt in range(max_checks):
                        time.sleep(check_interval)
                        try:
                            # Check if page is still alive
                            if page.is_closed():
                                print(f"[LocationSearcher] Page closed during URL polling")
                                break
                            
                            current_check_url = page.url
                            # Check if URL changed from initial homepage
                            if current_check_url != initial_url and current_check_url not in ['https://www.trulia.com/', 'https://www.trulia.com']:
                                final_url = current_check_url
                                elapsed = (check_attempt + 1) * check_interval
                                print(f"[LocationSearcher] ✓ URL change detected after {elapsed:.1f}s! {initial_url} → {final_url}")
                                break
                            elif check_attempt == max_checks - 1:
                                print(f"[LocationSearcher] ✗ URL did not change after {max_wait_seconds}s. Still at: {current_check_url}")
                                final_url = current_check_url
                        except Exception as poll_err:
                            # If browser closed, break immediately
                            if 'closed' in str(poll_err).lower() or 'target' in str(poll_err).lower():
                                print(f"[LocationSearcher] Browser closed during URL polling: {poll_err}")
                                break
                            print(f"[LocationSearcher] Error checking URL (attempt {check_attempt + 1}): {poll_err}")
                            if check_attempt == max_checks - 1:
                                try:
                                    if not page.is_closed():
                                        final_url = page.url
                                except:
                                    final_url = None
                
                # Get final URL if we don't have it yet
                if not final_url:
                    try:
                        final_url = page.url
                        print(f"[LocationSearcher] Retrieved final URL: {final_url}")
                    except Exception as url_error:
                        print(f"[LocationSearcher] Error getting final URL: {url_error}")
                        final_url = None
                
                # Check if we got a valid URL
                if final_url and 'trulia.com' in final_url and final_url not in ['https://www.trulia.com/', 'https://www.trulia.com']:
                    print(f"[LocationSearcher] ✓ Success! Returning URL: {final_url}")
                    try:
                        browser.close()
                    except:
                        pass
                    return final_url
                
                # If search submission failed, try constructing URL directly as fallback
                print(f"[LocationSearcher] Search submission didn't redirect. Trying URL construction fallback...")
                logger.info("[STATUS] Constructing URL directly...")
                constructed_url = cls._try_construct_trulia_url(location_clean)
                if constructed_url:
                    print(f"[LocationSearcher] ✓ Constructed URL: {constructed_url}")
                    logger.info(f"[STATUS] Using constructed URL: {constructed_url}")
                    # Return constructed URL directly - Trulia's URL pattern is reliable
                    # Format: /{STATE}/{City}/ (e.g., /MN/Minneapolis/)
                    try:
                        browser.close()
                    except:
                        pass
                    return constructed_url
                
                # Close browser before returning
                try:
                    browser.close()
                except:
                    pass
                
                return None
                
        except ImportError:
            print("[LocationSearcher] Playwright not installed - cannot use Browserless.io fallback")
            print("[LocationSearcher] Install with: pip install playwright && playwright install chromium")
            # Fallback to constructed URL if Playwright not available
            constructed_url = cls._try_construct_trulia_url(location_clean)
            if constructed_url:
                print(f"[LocationSearcher] Using constructed URL fallback: {constructed_url}")
                logger.info(f"[STATUS] Using constructed URL: {constructed_url}")
                return constructed_url
            return None
        except Exception as e:
            print(f"[LocationSearcher] Playwright error: {e}")
            import traceback
            print(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            # Try constructed URL as fallback
            constructed_url = cls._try_construct_trulia_url(location_clean)
            if constructed_url:
                print(f"[LocationSearcher] Using constructed URL fallback after error: {constructed_url}")
                logger.info(f"[STATUS] Using constructed URL: {constructed_url}")
                return constructed_url
            return None
    
    @classmethod
    def search_trulia(cls, location: str) -> Optional[str]:
        """
        Search Trulia for a location.
        Try Playwright first, but fallback to direct URL construction if browser automation fails.
        """
        location_clean = location.strip()
        logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
        
        # Try Playwright with Browserless.io first
        print(f"[LocationSearcher] Attempting browser automation with Playwright/Browserless.io...")
        result = cls._search_trulia_with_playwright(location_clean)
        
        if result:
            return result
        
        # If browser automation failed, try direct URL construction as final fallback
        print(f"[LocationSearcher] Browser automation failed, trying direct URL construction...")
        constructed_url = cls._try_construct_trulia_url(location_clean)
        if constructed_url:
            print(f"[LocationSearcher] Constructed URL: {constructed_url}")
            logger.info(f"[STATUS] Using constructed URL: {constructed_url}")
            # Return the constructed URL - caller will verify it works
            return constructed_url
        
        return None
    
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
            print(f"[LocationSearcher] Navigating to Apartments.com...")
            logger.info("[STATUS] Loading Apartments.com...")
            driver.get("https://www.apartments.com")
            
            # Wait a bit longer for page to fully load
            time.sleep(5)  # Increased wait time
            
            # Check what page actually loaded
            current_url = driver.current_url
            page_title = driver.title
            print(f"[LocationSearcher] Page loaded - URL: {current_url}")
            print(f"[LocationSearcher] Page title: {page_title}")
            
            # Check if page is blocked or redirected
            if 'apartments.com' not in current_url.lower():
                print(f"[LocationSearcher] WARNING: Page redirected or blocked. Current URL: {current_url}")
            
            # Wait for search box using WebDriverWait - Apartments.com uses specific ID
            # Use shorter timeout per selector to fail faster (5 seconds each)
            wait_short = WebDriverWait(driver, 5)  # 5 seconds per selector to fail faster
            
            print(f"[LocationSearcher] Waiting for Apartments.com search box to appear...")
            logger.info("[STATUS] Locating search box on Apartments.com...")
            
            # First, wait for page to be interactive (JavaScript loaded)
            try:
                print(f"[LocationSearcher] Waiting for page JavaScript to load...")
                driver.execute_script("return document.readyState")  # Check if JS is ready
                time.sleep(2)  # Additional wait for dynamic content
            except:
                pass
            
            # Try selectors in order of specificity - use WebDriverWait for each
            search_box = None
            search_selectors = [
                "input#quickSearchLookup",  # Specific ID from HTML provided
                "input.quickSearchLookup",  # Class name from HTML
                "input[aria-label='Location, School, or Point of Interest']",  # Exact aria-label match
                "input[placeholder='Location, School, or Point of Interest']",  # Exact placeholder match
                "input[aria-label*='Location, School']",  # Partial aria-label
                "input[placeholder*='Location, School']",  # Partial placeholder
            ]
            
            for selector in search_selectors:
                try:
                    print(f"[LocationSearcher] Trying selector: {selector}")
                    search_box = wait_short.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    # Check if element is visible and enabled
                    if search_box.is_displayed() and search_box.is_enabled():
                        logger.info(f"[LocationSearcher] ✓ Found Apartments.com search box with selector: {selector}")
                        print(f"[LocationSearcher] ✓ Found search box: {selector}")
                        break
                    else:
                        print(f"[LocationSearcher] Search box found but not visible/enabled: {selector}")
                        search_box = None
                except TimeoutException:
                    print(f"[LocationSearcher] Timeout waiting for selector: {selector} (5s)")
                    continue
                except Exception as e:
                    print(f"[LocationSearcher] Error with selector {selector}: {e}")
                    continue
            
            # Fallback: Try finding by iterating through all inputs if specific selectors failed
            if not search_box:
                print(f"[LocationSearcher] Specific selectors failed, trying fallback method...")
                try:
                    # Check page source first to see if search box exists
                    page_source_lower = driver.page_source.lower()
                    if 'quicksearchlookup' in page_source_lower:
                        print(f"[LocationSearcher] DEBUG: 'quickSearchLookup' found in page source but Selenium can't locate it")
                    else:
                        print(f"[LocationSearcher] DEBUG: 'quickSearchLookup' NOT in page source - page structure may differ")
                    
                    # Try to find any text inputs (with shorter timeout)
                    try:
                        wait_short.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input[type='text']")))
                    except:
                        # If no text inputs found at all, check for any inputs
                        print(f"[LocationSearcher] No text inputs found, checking for any input elements...")
                        try:
                            wait_short.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input")))
                        except:
                            print(f"[LocationSearcher] WARNING: No input elements found on page at all!")
                    
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type]), input")
                    print(f"[LocationSearcher] Found {len(all_inputs)} total inputs, checking each one...")
                    
                    for i, inp in enumerate(all_inputs[:10]):  # Limit to first 10 to save time
                        try:
                            if inp.is_displayed() and inp.is_enabled():
                                placeholder = (inp.get_attribute('placeholder') or '').lower()
                                aria_label = (inp.get_attribute('aria-label') or '').lower()
                                input_id = (inp.get_attribute('id') or '').lower()
                                input_class = (inp.get_attribute('class') or '').lower()
                                
                                print(f"[LocationSearcher] Input #{i}: id='{input_id}', class='{input_class[:40]}', placeholder='{placeholder[:40]}'")
                                
                                # Check for Apartments.com specific indicators
                                if ('quicksearch' in input_id or 
                                    'quicksearch' in input_class or
                                    'location, school' in placeholder or 
                                    'location, school' in aria_label or
                                    'point of interest' in placeholder):
                                    search_box = inp
                                    logger.info(f"[LocationSearcher] ✓ Found Apartments.com search box via fallback: id={input_id}, placeholder={placeholder[:50]}")
                                    print(f"[LocationSearcher] ✓ Found search box via fallback")
                                    break
                        except Exception as inp_err:
                            print(f"[LocationSearcher] Error checking input #{i}: {inp_err}")
                            continue
                    
                    # Last resort: use first visible text input
                    if not search_box and len(all_inputs) > 0:
                        print(f"[LocationSearcher] No matching input found, trying first visible input as last resort...")
                        for inp in all_inputs[:5]:  # Try first 5
                            try:
                                if inp.is_displayed() and inp.is_enabled():
                                    search_box = inp
                                    print(f"[LocationSearcher] Using first visible input as search box (last resort)")
                                    break
                            except:
                                continue
                except Exception as e:
                    print(f"[LocationSearcher] Fallback method error: {e}")
                    import traceback
                    print(f"[LocationSearcher] Fallback traceback: {traceback.format_exc()}")
                    import traceback
                    print(f"[LocationSearcher] Fallback traceback: {traceback.format_exc()}")
            
            if not search_box:
                # Get page info for debugging
                try:
                    page_source_snippet = driver.page_source[:500].lower()
                    page_source_length = len(driver.page_source)
                    print(f"[LocationSearcher] DEBUG: Page source length: {page_source_length} characters")
                    print(f"[LocationSearcher] DEBUG: Current URL: {driver.current_url}")
                    print(f"[LocationSearcher] DEBUG: Page title: {driver.title}")
                    print(f"[LocationSearcher] DEBUG: Page source preview: {driver.page_source[:300]}...")
                    
                    # Check if page might be blocked
                    if 'blocked' in page_source_snippet or 'access denied' in page_source_snippet or 'bot' in page_source_snippet:
                        print(f"[LocationSearcher] WARNING: Page might be blocked or detecting bot")
                    
                    # Check if quickSearchLookup exists at all in page source
                    if 'quicksearchlookup' in page_source_snippet or 'quickSearchLookup' in driver.page_source:
                        print(f"[LocationSearcher] DEBUG: Found 'quickSearchLookup' in page source but couldn't locate element")
                    else:
                        print(f"[LocationSearcher] DEBUG: 'quickSearchLookup' NOT found in page source - page structure may be different")
                except Exception as debug_err:
                    print(f"[LocationSearcher] Error getting debug info: {debug_err}")
                
                raise TimeoutException("Search box not found on Apartments.com after trying all selectors. Page may not have loaded correctly, structure is different, or page is blocking automated access.")
            
            # Get initial URL before search
            initial_url = driver.current_url
            print(f"[LocationSearcher] Initial URL: {initial_url}")
            
            # Clear the search box
            search_box.clear()
            time.sleep(0.5)
            
            # Enter location text
            search_box.send_keys(location_clean)
            logger.info(f"[LocationSearcher] Entered '{location_clean}' into Apartments.com search box")
            time.sleep(2.5)  # Wait for autocomplete suggestions to appear
            
            # IMPORTANT: Enter key does NOT work on Apartments.com
            # Must either: 1) Click first suggestion, OR 2) Click search button (button.typeaheadSearch)
            
            search_submitted = False
            
            # Method 1: Try clicking first autocomplete suggestion (preferred method)
            try:
                # Wait for suggestions to appear
                suggestions = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul[role='listbox'] li, div[class*='suggestion'] li, li[class*='suggestion'], div[role='option'], ul[class*='autocomplete'] li"))
                )
                
                if suggestions and len(suggestions) > 0:
                    # Click first autocomplete suggestion (preferred - works like user clicking)
                    suggestion_text = suggestions[0].text if hasattr(suggestions[0], 'text') else 'N/A'
                    logger.info(f"[LocationSearcher] Found {len(suggestions)} autocomplete suggestions, clicking first one: {suggestion_text[:50]}")
                    print(f"[LocationSearcher] Clicking first suggestion: {suggestion_text[:50]}")
                    suggestions[0].click()
                    search_submitted = True
                    time.sleep(3)  # Wait for redirect after clicking suggestion
                else:
                    # No suggestions - will use search button below
                    print(f"[LocationSearcher] No suggestions found, will use search button")
            except TimeoutException:
                # No suggestions appeared - will use search button instead
                print(f"[LocationSearcher] No autocomplete suggestions appeared, using search button")
            except Exception as sug_err:
                print(f"[LocationSearcher] Error finding suggestions: {sug_err}, using search button")
            
            # Method 2: Click search button (button.typeaheadSearch) - Enter key does NOT work
            if not search_submitted:
                try:
                    # Use the specific selector from HTML: button.typeaheadSearch
                    search_button = driver.find_element(By.CSS_SELECTOR, "button.typeaheadSearch")
                    logger.info(f"[LocationSearcher] Clicking search button (typeaheadSearch)")
                    print(f"[LocationSearcher] Clicking search button...")
                    search_button.click()
                    search_submitted = True
                    time.sleep(3)  # Wait for navigation
                except Exception as btn_err:
                    print(f"[LocationSearcher] Could not find/click search button: {btn_err}")
                    # Last resort: Try other button selectors
                    try:
                        alt_selectors = [
                            "button[title*='Search apartments']",
                            "button[aria-label*='Search apartments']",
                            "button[class*='search']",
                            "button[type='submit']",
                        ]
                        for selector in alt_selectors:
                            try:
                                btn = driver.find_element(By.CSS_SELECTOR, selector)
                                if btn.is_displayed():
                                    logger.info(f"[LocationSearcher] Clicking alternative search button: {selector}")
                                    btn.click()
                                    search_submitted = True
                                    time.sleep(3)
                                    break
                            except:
                                continue
                    except Exception as alt_err:
                        print(f"[LocationSearcher] All search button methods failed: {alt_err}")
                        # Do NOT use Enter key - it doesn't work on Apartments.com
                        logger.warning(f"[LocationSearcher] Enter key does not work on Apartments.com - search may fail")
            
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
