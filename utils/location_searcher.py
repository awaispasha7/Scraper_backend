"""
Location Search Utilities
Searches platforms to get the actual listing URL from a location name
Uses Selenium WebDriver with Zyte proxy (direct config, same as existing scrapers)
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
    def _should_use_headless(cls) -> bool:
        """
        Check if browser should run in headless mode.
        Can be toggled via HEADLESS_BROWSER environment variable.
        Default: True (headless)
        Set HEADLESS_BROWSER=false to see browser window
        """
        headless_env = os.getenv("HEADLESS_BROWSER", "true").lower()
        use_headless = headless_env not in ["false", "0", "no", "off"]
        if not use_headless:
            print(f"[LocationSearcher] ⚠️ Running in NON-HEADLESS mode (HEADLESS_BROWSER=false)")
        return use_headless
    
    @classmethod
    def _get_driver(cls, use_zyte_proxy: bool = True):
        """
        Create and return a Chrome WebDriver instance with optional Zyte proxy.
        Uses the same direct proxy configuration approach as the existing scrapers.
        
        Args:
            use_zyte_proxy: If True and ZYTE_API_KEY is available, use Zyte proxy.
                            If False or key not available, use local Chrome without proxy.
        """
        import os
        import sys
        
        # Initialize chrome_options
        chrome_options = Options()
        
        # Check if we should use Zyte proxy (same pattern as scrapers use)
        zyte_api_key = None
        if use_zyte_proxy:
            zyte_api_key = os.getenv("ZYTE_API_KEY")
            if zyte_api_key:
                # Use direct proxy configuration like the scrapers do
                # Same format as: ZYTE_PROXY = f'http://{ZYTE_API_KEY}:@api.zyte.com:8011'
                zyte_proxy = f"http://{zyte_api_key}:@api.zyte.com:8011"
                chrome_options.add_argument(f'--proxy-server={zyte_proxy}')
                print(f"[LocationSearcher] Using Zyte proxy: api.zyte.com:8011")
                logger.info("[LocationSearcher] Configuring Selenium with Zyte proxy (direct config)")
            else:
                print(f"[LocationSearcher] ZYTE_API_KEY not found, using local Chrome without proxy")
                logger.info("[LocationSearcher] Using local Chrome without proxy")
        else:
            print(f"[LocationSearcher] Not using Zyte proxy (use_zyte_proxy=False)")
        
        # If we got here, chrome_options is already initialized
        
        # Configure Chrome options for regular Selenium
        # Check environment variable for headless mode (default: headless)
        use_headless = cls._should_use_headless()
        if use_headless:
            chrome_options.add_argument('--headless=new')
        else:
            print(f"[LocationSearcher] Running Chrome in visible mode (non-headless)")
        
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
                "images": 1
            },
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # Use Chrome/Chromium (with or without Zyte proxy)
            if zyte_api_key:
                print("[LocationSearcher] Using Selenium with Zyte proxy")
            else:
                print("[LocationSearcher] Using local Chrome/Chromium")
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
            
            if zyte_api_key:
                print(f"[LocationSearcher] ✓ Chrome driver created with Zyte proxy")
            else:
                print(f"[LocationSearcher] ✓ Chrome driver created (no proxy)")
            
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
        Search Trulia for a location using multiple strategies in order:
        1. Playwright (best for bot detection bypass)
        2. Selenium (fallback)
        3. URL construction (final fallback)
        
        Note: Puppeteer is Node.js only, so we skip it and use Playwright (Python equivalent) instead.
        Requested order: Playwright -> Puppeteer -> Selenium -> URL construct
        Actual implementation: Playwright -> Selenium -> URL construct (Puppeteer skipped)
        """
        location_clean = location.strip()
        logger.info(f"[LocationSearcher] Searching Trulia for: {location_clean}")
        
        # Strategy 1: Try Playwright first (best for bot detection bypass)
        print(f"[LocationSearcher] [1/4] Trying Playwright...")
        result = cls._search_trulia_with_playwright(location_clean)
        if result:
            print(f"[LocationSearcher] ✓ Playwright succeeded!")
            return result
        print(f"[LocationSearcher] ✗ Playwright failed")
        
        # Strategy 2: Puppeteer (skipped - Node.js only, not available in Python)
        print(f"[LocationSearcher] [2/4] Skipping Puppeteer (Node.js only, not available in Python)")
        
        # Strategy 3: Fallback to Selenium
        print(f"[LocationSearcher] [3/4] Trying Selenium...")
        result = cls._search_trulia_with_selenium(location_clean)
        if result:
            print(f"[LocationSearcher] ✓ Selenium succeeded!")
            return result
        print(f"[LocationSearcher] ✗ Selenium failed")
        
        # Strategy 4: Final fallback to URL construction
        print(f"[LocationSearcher] [4/4] Using URL construction fallback...")
        result = cls._try_construct_trulia_url(location_clean)
        if result:
            print(f"[LocationSearcher] ✓ URL construction succeeded!")
        else:
            print(f"[LocationSearcher] ✗ All strategies failed")
        return result
    
    @classmethod
    def _search_trulia_with_playwright(cls, location: str) -> Optional[str]:
        """Search Trulia using Playwright (primary method)."""
        try:
            from playwright.sync_api import sync_playwright
            
            print(f"[LocationSearcher] Trying Playwright for Trulia: {location}")
            logger.info(f"[LocationSearcher] Using Playwright for Trulia search")
            
            with sync_playwright() as p:
                # Check environment variable for headless mode (default: headless)
                use_headless = cls._should_use_headless()
                
                # Launch browser with stealth settings
                browser = p.chromium.launch(
                    headless=use_headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                
                if not use_headless:
                    print(f"[LocationSearcher] ⚠️ Playwright running in NON-HEADLESS mode - browser window will be visible")
                
                # Create context with realistic settings
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                    }
                )
                
                # Add stealth scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                """)
                
                page = context.new_page()
                print(f"[LocationSearcher] Navigating to Trulia...")
                
                # Navigate to Trulia
                try:
                    page.goto("https://www.trulia.com", wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)  # Wait for page to load
                except Exception as e:
                    print(f"[LocationSearcher] Failed to load Trulia page: {e}")
                    browser.close()
                    return None
                
                # Check if page is blocked
                page_title = page.title().lower()
                if 'access denied' in page_title or 'captcha' in page_title or 'blocked' in page_title:
                    print(f"[LocationSearcher] Page appears blocked: {page.title()}")
                    browser.close()
                    return None
                
                print(f"[LocationSearcher] Looking for Trulia search box with Playwright...")
                
                # Use exact selectors from Trulia's actual HTML structure
                # Input ID: banner-search, Placeholder: "Search for City, Neighborhood, Zip, County, School"
                search_selectors = [
                    "input#banner-search",  # Most reliable - exact ID
                    "input[aria-label='Search for City, Neighborhood, Zip, County, School']",  # Exact aria-label
                    "input[placeholder='Search for City, Neighborhood, Zip, County, School']",  # Exact placeholder
                    "input.react-autosuggest__input",  # Class name
                    "input[role='combobox'][id='banner-search']",  # Role + ID combo
                ]
                
                search_box = None
                for selector in search_selectors:
                    try:
                        print(f"[LocationSearcher] Trying selector: {selector}")
                        search_box = page.query_selector(selector)
                        if search_box:
                            # Check if visible
                            try:
                                if search_box.is_visible():
                                    print(f"[LocationSearcher] ✓ Found Trulia search box: {selector}")
                                    break
                            except:
                                # If is_visible() fails, try waiting for it
                                page.wait_for_selector(selector, state="visible", timeout=5000)
                                search_box = page.query_selector(selector)
                                if search_box:
                                    print(f"[LocationSearcher] ✓ Found Trulia search box (after wait): {selector}")
                                    break
                    except Exception as e:
                        print(f"[LocationSearcher] Error with selector {selector}: {e}")
                        continue
                
                # Fallback: try finding by placeholder text if exact match fails
                if not search_box:
                    try:
                        print(f"[LocationSearcher] Trying placeholder text search as fallback...")
                        all_inputs = page.query_selector_all("input[type='text'], input[role='combobox']")
                        for inp in all_inputs:
                            try:
                                if inp.is_visible():
                                    placeholder = (inp.get_attribute('placeholder') or '').lower()
                                    aria_label = (inp.get_attribute('aria-label') or '').lower()
                                    inp_id = inp.get_attribute('id') or ''
                                    # Look for key indicators
                                    if (inp_id == 'banner-search' or 
                                        'search for city' in placeholder or 
                                        'search for city' in aria_label):
                                        search_box = inp
                                        print(f"[LocationSearcher] ✓ Found Trulia search box by fallback search")
                                        break
                            except:
                                continue
                    except Exception as e:
                        print(f"[LocationSearcher] Placeholder search failed: {e}")
                
                if not search_box:
                    print(f"[LocationSearcher] Search box not found with Playwright")
                    browser.close()
                    return None
                
                # Click and clear search box
                search_box.click()
                time.sleep(0.5)
                search_box.fill("")  # Clear
                time.sleep(0.5)
                
                # Type location
                print(f"[LocationSearcher] Typing location: {location}")
                search_box.fill(location)
                time.sleep(2)  # Wait for autocomplete
                
                # Wait for suggestions to appear (they're in element with id="react-autowhatever-home-banner")
                search_submitted = False
                try:
                    # Wait for suggestions container to appear
                    suggestions_container = page.wait_for_selector("#react-autowhatever-home-banner", timeout=5000)
                    if suggestions_container:
                        print(f"[LocationSearcher] Suggestions container appeared")
                        time.sleep(1)  # Give suggestions time to render
                        
                        # Get all suggestion items
                        suggestions = page.query_selector_all(
                            "#react-autowhatever-home-banner li, "
                            "#react-autowhatever-home-banner [role='option'], "
                            "#react-autowhatever-home-banner [data-suggestion-index]"
                        )
                        
                        if suggestions:
                            print(f"[LocationSearcher] Found {len(suggestions)} suggestions")
                            # Filter suggestions - look for actual location matches
                            for sug in suggestions:
                                try:
                                    text = sug.inner_text().lower().strip()
                                    # Skip non-location suggestions
                                    if any(skip in text for skip in ['current location', 'search by commute', 'popular searches', 'commute time']):
                                        continue
                                    # Look for location matches (should contain city name or have comma for city,state)
                                    if location.lower() in text or (',' in text and len(text.split(',')) == 2):
                                        print(f"[LocationSearcher] Clicking suggestion: {sug.inner_text()[:50]}")
                                        sug.click()
                                        search_submitted = True
                                        time.sleep(3)
                                        print(f"[LocationSearcher] ✓ Clicked suggestion")
                                        break
                                except Exception as e:
                                    print(f"[LocationSearcher] Error clicking suggestion: {e}")
                                    continue
                        
                        # If no good suggestion found, try clicking first non-filtered one
                        if not search_submitted and suggestions:
                            try:
                                first_sug = suggestions[0]
                                text = first_sug.inner_text().lower()
                                if 'current location' not in text and 'commute' not in text:
                                    print(f"[LocationSearcher] Clicking first available suggestion: {first_sug.inner_text()[:50]}")
                                    first_sug.click()
                                    search_submitted = True
                                    time.sleep(3)
                            except:
                                pass
                except Exception as e:
                    print(f"[LocationSearcher] Error waiting for suggestions: {e}")
                
                if not search_submitted:
                    # Press Enter as fallback
                    print(f"[LocationSearcher] No suggestions clicked, pressing Enter...")
                    search_box.press("Enter")
                    time.sleep(3)
                
                # Wait for navigation
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    time.sleep(2)  # Fallback wait
                
                final_url = page.url
                print(f"[LocationSearcher] Playwright final URL: {final_url}")
                logger.info(f"[LocationSearcher] Trulia Playwright final URL: {final_url}")
                
                browser.close()
                
                if 'trulia.com' in final_url and final_url != 'https://www.trulia.com' and final_url != 'https://www.trulia.com/':
                    return final_url
                
                return None
                
        except ImportError:
            print(f"[LocationSearcher] Playwright not available")
            logger.warning(f"[LocationSearcher] Playwright not installed")
            return None
        except Exception as e:
            print(f"[LocationSearcher] Playwright error: {e}")
            logger.error(f"[LocationSearcher] Playwright error for Trulia: {e}")
            import traceback
            print(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            return None
    
    @classmethod
    def _search_trulia_with_selenium(cls, location: str) -> Optional[str]:
        """Search Trulia using Selenium (fallback method)."""
        driver = None
        try:
            location_clean = location.strip()
            print(f"[LocationSearcher] Trying Selenium for Trulia: {location_clean}")
            
            driver = cls._get_driver(use_zyte_proxy=False)
            driver.get("https://www.trulia.com")
            
            wait = WebDriverWait(driver, 20)
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(3)
            except:
                time.sleep(5)
            
            print(f"[LocationSearcher] Looking for Trulia search box with Selenium...")
            
            # Check if page is blocked
            page_title = driver.title.lower()
            if 'access denied' in page_title or 'captcha' in page_title or 'blocked' in page_title:
                print(f"[LocationSearcher] Page appears blocked: {driver.title}")
                return None
            
            search_box = None
            
            # Use exact selectors from Trulia's actual HTML structure
            search_selectors = [
                "input#banner-search",  # Most reliable - exact ID
                "input[aria-label='Search for City, Neighborhood, Zip, County, School']",  # Exact aria-label
                "input[placeholder='Search for City, Neighborhood, Zip, County, School']",  # Exact placeholder
                "input.react-autosuggest__input",  # Class name
                "input[role='combobox'][id='banner-search']",  # Role + ID combo
            ]
            
            for selector in search_selectors:
                try:
                    print(f"[LocationSearcher] Trying selector: {selector}")
                    search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if search_box.is_displayed() and search_box.is_enabled():
                        print(f"[LocationSearcher] ✓ Found Trulia search box with Selenium: {selector}")
                        break
                    else:
                        search_box = None
                except:
                    continue
                
                if search_box:
                    break
            
            # Find by placeholder/aria-label as fallback
            if not search_box:
                try:
                    print(f"[LocationSearcher] Trying placeholder/aria-label search as fallback...")
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[role='combobox']")
                    for inp in all_inputs:
                        try:
                            if inp.is_displayed() and inp.is_enabled():
                                inp_id = inp.get_attribute('id') or ''
                                placeholder = (inp.get_attribute('placeholder') or '').lower()
                                aria_label = (inp.get_attribute('aria-label') or '').lower()
                                # Look for exact matches
                                if (inp_id == 'banner-search' or 
                                    'search for city, neighborhood' in placeholder or 
                                    'search for city, neighborhood' in aria_label):
                                    search_box = inp
                                    print(f"[LocationSearcher] ✓ Found Trulia search box by fallback search")
                                    break
                        except:
                            continue
                except Exception as e:
                    print(f"[LocationSearcher] Fallback search failed: {e}")
            
            if not search_box:
                print(f"[LocationSearcher] Search box not found with Selenium")
                return None
            
            # Interact with search box
            search_box.click()
            time.sleep(0.5)
            search_box.clear()
            time.sleep(0.5)
            search_box.send_keys(location_clean)
            time.sleep(2)
            
            # Try suggestions or Enter
            # Suggestions are in element with id="react-autowhatever-home-banner"
            search_submitted = False
            try:
                # Wait for suggestions container
                suggestions_container = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "react-autowhatever-home-banner"))
                )
                if suggestions_container:
                    print(f"[LocationSearcher] Suggestions container appeared")
                    time.sleep(1)  # Give suggestions time to render
                    
                    # Get suggestion items
                    suggestions = driver.find_elements(By.CSS_SELECTOR, 
                        "#react-autowhatever-home-banner li, "
                        "#react-autowhatever-home-banner [role='option'], "
                        "#react-autowhatever-home-banner [data-suggestion-index]"
                    )
                    
                    if suggestions:
                        print(f"[LocationSearcher] Found {len(suggestions)} suggestions")
                        for sug in suggestions:
                            try:
                                text = sug.text.lower().strip()
                                # Skip non-location suggestions
                                if any(skip in text for skip in ['current location', 'search by commute', 'commute time']):
                                    continue
                                # Look for location matches
                                if location_clean.lower() in text or (',' in text and len(text.split(',')) == 2):
                                    print(f"[LocationSearcher] Clicking suggestion: {sug.text[:50]}")
                                    sug.click()
                                    search_submitted = True
                                    time.sleep(3)
                                    print(f"[LocationSearcher] ✓ Clicked suggestion")
                                    break
                            except Exception as e:
                                print(f"[LocationSearcher] Error clicking suggestion: {e}")
                                continue
                        
                        # If no good match, try first non-filtered suggestion
                        if not search_submitted and suggestions:
                            try:
                                first_sug = suggestions[0]
                                text = first_sug.text.lower()
                                if 'current location' not in text and 'commute' not in text:
                                    print(f"[LocationSearcher] Clicking first available suggestion: {first_sug.text[:50]}")
                                    first_sug.click()
                                    search_submitted = True
                                    time.sleep(3)
                            except:
                                pass
            except Exception as e:
                print(f"[LocationSearcher] Error waiting for suggestions: {e}")
            
            if not search_submitted:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            final_url = driver.current_url
            print(f"[LocationSearcher] Selenium final URL: {final_url}")
            logger.info(f"[LocationSearcher] Trulia Selenium final URL: {final_url}")
            
            if 'trulia.com' in final_url and final_url != 'https://www.trulia.com':
                return final_url
            
            return None
            
        except Exception as e:
            logger.error(f"[LocationSearcher] Selenium error for Trulia: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    @classmethod
    def search_apartments(cls, location: str) -> Optional[str]:
        """
        Search Apartments.com for a location using Selenium with Zyte proxy.
        The search box has a prefilled value that needs to be clicked to reveal the placeholder.
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Apartments.com for: {location_clean}")
            
            # Try without proxy first - Zyte proxy doesn't work well with Selenium interactive automation
            # Main scrapers use scrapy-zyte-api (HTTP), not Selenium proxy
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
            driver.get("https://www.apartments.com")
            
            wait = WebDriverWait(driver, 25)
            # Wait for page to load
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(4)  # Additional wait for dynamic content
            except:
                time.sleep(6)  # Fallback wait
            
            # Check if page is blocked
            page_title = driver.title.lower()
            page_source = driver.page_source.lower()
            if 'access denied' in page_title or 'captcha' in page_source or 'blocked' in page_title:
                print(f"[LocationSearcher] ⚠️ Page may be blocked: {driver.title}")
                logger.warning(f"[LocationSearcher] Apartments.com page may be blocked: {driver.title}")
            
            print(f"[LocationSearcher] Looking for Apartments.com search box...")
            
            # Strategy 1: Try to find search box by ID first (most reliable)
            search_box = None
            try:
                # Wait for element to be clickable (ensures it's visible)
                search_box = wait.until(EC.element_to_be_clickable((By.ID, "quickSearchLookup")))
                print(f"[LocationSearcher] ✓ Found search box by ID: quickSearchLookup")
            except TimeoutException:
                print(f"[LocationSearcher] ID not found, trying alternative selectors...")
                
                # Strategy 2: Try alternative selectors
                search_selectors = [
                    "input.quickSearchLookup",
                    "input[aria-label='Location, School, or Point of Interest']",
                    "input[placeholder='Location, School, or Point of Interest']",
                    "input[placeholder*='Location, School' i]",
                    "input[aria-label*='Location' i]",
                ]
                
                for selector in search_selectors:
                    try:
                        print(f"[LocationSearcher] Trying selector: {selector}")
                        search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        print(f"[LocationSearcher] ✓ Found search box: {selector}")
                        break
                    except TimeoutException:
                        continue
                    except Exception as e:
                        print(f"[LocationSearcher] Error with selector {selector}: {e}")
                        continue
            
            # Strategy 3: Find by placeholder text (like FSBO)
            if not search_box:
                try:
                    print(f"[LocationSearcher] Trying placeholder text search...")
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[placeholder]")
                    for inp in all_inputs:
                        try:
                            if inp.is_displayed() and inp.is_enabled():
                                placeholder = (inp.get_attribute('placeholder') or '').lower()
                                aria_label = (inp.get_attribute('aria-label') or '').lower()
                                # Look for "Location, School, or Point of Interest"
                                if 'location' in placeholder or 'location' in aria_label:
                                    if 'school' in placeholder or 'point of interest' in placeholder:
                                        search_box = inp
                                        print(f"[LocationSearcher] ✓ Found Apartments.com search box by placeholder/aria-label")
                                        logger.info(f"[LocationSearcher] Found Apartments.com search box by placeholder: {placeholder[:50]}...")
                                        break
                        except:
                            continue
                except Exception as e:
                    print(f"[LocationSearcher] Placeholder search failed: {e}")
            
            if not search_box:
                raise TimeoutException("Search box not found on Apartments.com after trying all strategies")
            
            # Click the search box first to reveal placeholder and clear prefilled value
            print(f"[LocationSearcher] Clicking search box to reveal placeholder...")
            try:
                # Scroll element into view if needed
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_box)
                time.sleep(0.5)
            except:
                pass
            
            # Click to focus and clear prefilled value
            search_box.click()
            time.sleep(1)  # Wait for placeholder to appear
            
            # Clear any existing value
            search_box.clear()
            time.sleep(0.5)
            
            # Also try Ctrl+A to select all and delete, in case clear() didn't work
            try:
                search_box.send_keys(Keys.CONTROL + "a")
                time.sleep(0.3)
                search_box.send_keys(Keys.DELETE)
                time.sleep(0.5)
            except:
                pass
            
            print(f"[LocationSearcher] Typing location: {location_clean}")
            # Type the location character by character (more human-like)
            for char in location_clean:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            time.sleep(2.5)  # Wait for autocomplete suggestions to appear
            
            print(f"[LocationSearcher] Looking for autocomplete suggestions...")
            # Try clicking first suggestion or search button
            search_submitted = False
            
            # First, try to find and click autocomplete suggestions
            try:
                # Wait for suggestions to appear
                suggestions_wait = WebDriverWait(driver, 5)
                suggestions = suggestions_wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul[role='listbox'] li, div[role='option'], ul.autocompleteList li, div.typeaheadItem"))
                )
                if suggestions:
                    print(f"[LocationSearcher] Found {len(suggestions)} suggestions, clicking first one...")
                    # Scroll suggestion into view
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", suggestions[0])
                    time.sleep(0.5)
                    suggestions[0].click()
                    search_submitted = True
                    time.sleep(3)
                    print(f"[LocationSearcher] ✓ Clicked first suggestion")
            except TimeoutException:
                print(f"[LocationSearcher] No suggestions found, trying search button...")
            
            # If no suggestions, try clicking the search button
            if not search_submitted:
                try:
                    # Look for search button (magnifying glass icon)
                    button_selectors = [
                        "button.typeaheadSearch",
                        "button[type='submit']",
                        "button[aria-label*='search' i]",
                        "button[class*='search' i]",
                        "svg[class*='search']",
                    ]
                    
                    for selector in button_selectors:
                        try:
                            button = driver.find_element(By.CSS_SELECTOR, selector)
                            if button.is_displayed():
                                print(f"[LocationSearcher] Found search button: {selector}")
                                button.click()
                                search_submitted = True
                                time.sleep(3)
                                print(f"[LocationSearcher] ✓ Clicked search button")
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"[LocationSearcher] Could not find search button: {e}")
            
            # Last resort: press Enter
            if not search_submitted:
                print(f"[LocationSearcher] Pressing Enter as last resort...")
                try:
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(3)
                    search_submitted = True
                except:
                    pass
            
            # Get final URL
            final_url = driver.current_url
            print(f"[LocationSearcher] Initial URL: https://www.apartments.com")
            print(f"[LocationSearcher] Final URL: {final_url}")
            logger.info(f"[LocationSearcher] Apartments.com final URL: {final_url}")
            
            # Verify we got a different URL (navigation occurred)
            if 'apartments.com' in final_url and final_url != 'https://www.apartments.com' and final_url != 'https://www.apartments.com/':
                return final_url
            
            print(f"[LocationSearcher] ⚠️ URL did not change, search may have failed")
            return None
            
        except TimeoutException as e:
            logger.error(f"[LocationSearcher] Timeout waiting for Apartments.com search box: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching Apartments.com: {e}")
            import traceback
            print(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    @classmethod
    def _search_apartments_with_zyte(cls, location: str, zyte_api_key: str) -> Optional[str]:
        """
        Search Apartments.com using Playwright with Zyte Smart Proxy Manager.
        Zyte provides residential proxies and better bot detection bypass.
        """
        try:
            from playwright.sync_api import sync_playwright
            
            location_clean = location.strip()
            print(f"[LocationSearcher] Trying Zyte Smart Proxy Manager with Playwright for Apartments.com: {location_clean}")
            
            with sync_playwright() as p:
                print(f"[LocationSearcher] Launching browser with Zyte Smart Proxy Manager...")
                
                # Launch browser with Zyte proxy (Smart Proxy Manager format)
                # Zyte Smart Proxy Manager uses: http://api_key:@proxy.zyte.com:8011
                browser = p.chromium.launch(
                    headless=True,
                    proxy={
                        "server": "http://proxy.zyte.com:8011",
                        "username": zyte_api_key,
                        "password": "",  # Zyte uses API key as username
                    }
                )
                
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                    }
                )
                
                # Add stealth scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                """)
                
                page = context.new_page()
                print(f"[LocationSearcher] Navigating to Apartments.com via Zyte Smart Proxy...")
                
                try:
                    page.goto("https://www.apartments.com", wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)
                except Exception as e:
                    print(f"[LocationSearcher] Failed to load page via Zyte: {e}")
                    browser.close()
                    return None
                
                # Check if page loaded successfully
                page_title = page.title()
                if 'access denied' in page_title.lower():
                    print(f"[LocationSearcher] Page still blocked with Zyte Smart Proxy Manager")
                    browser.close()
                    return None
                
                # Find search box and perform search
                search_box = None
                for selector in ["input#quickSearchLookup", "input.quickSearchLookup", 
                                "input[aria-label='Location, School, or Point of Interest']"]:
                    try:
                        search_box = page.query_selector(selector)
                        if search_box and search_box.is_visible():
                            break
                    except:
                        continue
                
                if not search_box:
                    print(f"[LocationSearcher] Search box not found with Zyte")
                    browser.close()
                    return None
                
                # Perform search
                search_box.click()
                time.sleep(0.5)
                search_box.fill(location_clean)
                time.sleep(2.5)
                
                # Try to click suggestion or search button
                try:
                    suggestion = page.query_selector("ul[role='listbox'] li")
                    if suggestion and suggestion.is_visible():
                        suggestion.click()
                        time.sleep(3)
                    else:
                        button = page.query_selector("button.typeaheadSearch")
                        if button:
                            button.click()
                            time.sleep(3)
                except:
                    pass
                
                # Get final URL
                final_url = page.url
                browser.close()
                
                if 'apartments.com' in final_url and final_url != 'https://www.apartments.com':
                    print(f"[LocationSearcher] ✓ Success with Zyte! URL: {final_url}")
                    return final_url
                
                return None
                
        except ImportError:
            print("[LocationSearcher] Playwright not installed for Zyte Smart Proxy")
            return None
        except Exception as e:
            print(f"[LocationSearcher] Zyte Smart Proxy error: {e}")
            import traceback
            print(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            return None
    
    @classmethod
    def _search_apartments_with_playwright(cls, location: str) -> Optional[str]:
        """
        Search Apartments.com using Playwright.
        Tries Zyte Smart Proxy Manager first (if available), then falls back to Browserless.io.
        """
        try:
            from playwright.sync_api import sync_playwright
            
            # Try Zyte Smart Proxy Manager first (if API key available)
            zyte_api_key = os.getenv("ZYTE_API_KEY")
            if zyte_api_key:
                print("[LocationSearcher] ZYTE_API_KEY found - trying Zyte Smart Proxy Manager with Playwright")
                result = cls._search_apartments_with_zyte(location, zyte_api_key)
                if result:
                    return result
                print("[LocationSearcher] Zyte Smart Proxy Manager failed, falling back to Browserless.io")
            
            # Fallback to Browserless.io
            browserless_token = os.getenv("BROWSERLESS_TOKEN")
            if not browserless_token:
                print("[LocationSearcher] No BROWSERLESS_TOKEN or ZYTE_API_KEY - cannot use Playwright for Apartments.com")
                return None
            
            browserless_token = browserless_token.strip()
            location_clean = location.strip()
            print(f"[LocationSearcher] Trying Playwright with Browserless.io for Apartments.com: {location_clean}")
            
            # Get region (default: sfo)
            region = os.getenv("BROWSERLESS_REGION", "sfo").lower()
            if region not in ["sfo", "lon", "ams"]:
                region = "sfo"
            
            # Browserless.io WebSocket endpoint for CDP connection with stealth mode
            browserless_url = f"wss://production-{region}.browserless.io?token={browserless_token}&stealth=true"
            
            with sync_playwright() as p:
                print(f"[LocationSearcher] Connecting to Browserless.io via Playwright CDP...")
                print(f"[LocationSearcher] Endpoint: wss://production-{region}.browserless.io (region: {region}, stealth: true)")
                
                browser = p.chromium.connect_over_cdp(browserless_url)
                print(f"[LocationSearcher] Successfully connected to Browserless.io")
                
                # Create a fresh context with stealth settings
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
                
                # Add comprehensive stealth scripts (similar to Trulia)
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
                
                # Navigate to Apartments.com
                print(f"[LocationSearcher] Navigating to Apartments.com...")
                logger.info("[STATUS] Bypassing bot detection... This may take 30-60 seconds")
                print(f"[LocationSearcher] [STATUS] Bypassing bot detection... This may take 30-60 seconds")
                
                try:
                    page.goto("https://www.apartments.com", wait_until="domcontentloaded", timeout=60000)
                    time.sleep(2)  # Initial wait
                    
                    # Add human-like behavior: scroll down and back up
                    try:
                        page.evaluate("window.scrollTo(0, 300)")
                        time.sleep(0.5)
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.5)
                    except:
                        pass
                except Exception as goto_error:
                    if "timeout" in str(goto_error).lower():
                        logger.warning("[STATUS] Page load timeout - retrying...")
                        try:
                            page.goto("https://www.apartments.com", wait_until="networkidle", timeout=90000)
                            time.sleep(2)
                            # Add human-like behavior on retry too
                            try:
                                page.evaluate("window.scrollTo(0, 300)")
                                time.sleep(0.5)
                                page.evaluate("window.scrollTo(0, 0)")
                                time.sleep(0.5)
                            except:
                                pass
                        except Exception as retry_error:
                            logger.error(f"Failed to load Apartments.com after retry: {retry_error}")
                            return None
                    else:
                        return None
                
                # Wait and check for search box multiple times (like Trulia)
                # This gives the page time to process and bypass bot detection
                print(f"[LocationSearcher] Checking for search box (waiting up to 15 seconds)...")
                logger.info("[STATUS] Waiting for page to fully load and checking for bot detection...")
                print(f"[LocationSearcher] [STATUS] Waiting for page to fully load and checking for bot detection...")
                
                search_box = None
                search_box_selectors = [
                    "input#quickSearchLookup",
                    "input.quickSearchLookup",
                    "input[aria-label='Location, School, or Point of Interest']",
                    "input[placeholder='Location, School, or Point of Interest']",
                    "input[aria-label*='Location, School']",
                    "input[placeholder*='Location, School']",
                ]
                
                # Try multiple times with delays (up to 5 attempts, 3 seconds apart)
                for attempt in range(5):
                    for selector in search_box_selectors:
                        try:
                            search_box = page.query_selector(selector)
                            if search_box:
                                try:
                                    if search_box.is_visible():
                                        print(f"[LocationSearcher] ✓ Search box found and visible: {selector}")
                                        break
                                except:
                                    # If visibility check fails, try to use it anyway
                                    print(f"[LocationSearcher] ✓ Search box found (visibility uncertain): {selector}")
                                    break
                        except:
                            continue
                    
                    if search_box:
                        break
                    
                    if attempt < 4:
                        print(f"[LocationSearcher] Search box not found yet, waiting 3 more seconds... (attempt {attempt + 2}/5)")
                        time.sleep(3)
                
                # If search box not found, check for explicit blocking
                if not search_box:
                    print(f"[LocationSearcher] Search box not found. Checking for blocking messages...")
                    page_title = page.title()
                    page_content = page.content().lower()
                    current_url = page.url
                    print(f"[LocationSearcher] Page title: {page_title}, URL: {current_url}")
                    
                    # Check for explicit blocking messages in content (not just title)
                    explicit_blocking = (
                        "access denied" in page_title.lower() or
                        "access denied" in page_content or
                        "blocked" in page_title.lower() or
                        ("blocked" in page_content and "access" in page_content) or
                        "please verify you are human" in page_content
                    )
                    
                    if explicit_blocking:
                        print(f"[LocationSearcher] Page explicitly blocked - Access Denied message detected")
                        return None
                    else:
                        # Page loaded but search box not found - might be a different structure
                        print(f"[LocationSearcher] Page loaded but search box not found - page structure may differ")
                        return None
            
                # Get initial URL
                initial_url = page.url
                print(f"[LocationSearcher] Initial URL: {initial_url}")
                
                # Fill search box
                print(f"[LocationSearcher] Entering location '{location_clean}' into search box...")
                logger.info(f"[STATUS] Searching for: {location_clean}")
                search_box.click()
                time.sleep(0.5)
                search_box.fill("")  # Clear
                search_box.fill(location_clean)  # Type location
                time.sleep(2.5)  # Wait for autocomplete suggestions
                
                search_submitted = False
                
                # Method 1: Click first autocomplete suggestion (preferred)
                try:
                    # Wait for suggestions
                    time.sleep(1)
                    suggestion_selectors = [
                        "ul[role='listbox'] li",
                        "div[role='listbox'] div",
                        "ul[class*='autocomplete'] li",
                        "li[class*='suggestion']",
                        "div[role='option']",
                    ]
                    
                    suggestion = None
                    for selector in suggestion_selectors:
                        try:
                            suggestions = page.query_selector_all(selector)
                            if suggestions:
                                for sug in suggestions:
                                    try:
                                        if sug.is_visible():
                                            text = sug.inner_text().lower()
                                            # Skip generic suggestions
                                            if any(skip in text for skip in ['current location', 'popular searches']):
                                                continue
                                            # If it contains our location or looks like a location
                                            if location_clean.lower() in text or ',' in text:
                                                suggestion = sug
                                                print(f"[LocationSearcher] Found suggestion: {text[:50]}")
                                                break
                                    except:
                                        continue
                                if suggestion:
                                    break
                        except:
                            continue
                    
                    if suggestion:
                        print(f"[LocationSearcher] Clicking first autocomplete suggestion...")
                        suggestion.click()
                        search_submitted = True
                        time.sleep(3)  # Wait for navigation
                except Exception as sug_err:
                    print(f"[LocationSearcher] Error with suggestions: {sug_err}")
                
                # Method 2: Click search button (button.typeaheadSearch) - Enter key does NOT work
                if not search_submitted:
                    try:
                        search_button = page.query_selector("button.typeaheadSearch")
                        if search_button and search_button.is_visible():
                            print(f"[LocationSearcher] Clicking search button (typeaheadSearch)...")
                            logger.info("[STATUS] Submitting search...")
                            search_button.click()
                            search_submitted = True
                            time.sleep(3)  # Wait for navigation
                        else:
                            # Try alternative button selectors
                            alt_selectors = [
                                "button[title*='Search apartments']",
                                "button[aria-label*='Search apartments']",
                                "button[class*='search']",
                            ]
                            for selector in alt_selectors:
                                try:
                                    btn = page.query_selector(selector)
                                    if btn and btn.is_visible():
                                        print(f"[LocationSearcher] Clicking alternative search button: {selector}")
                                        btn.click()
                                        search_submitted = True
                                        time.sleep(3)
                                        break
                                except:
                                    continue
                    except Exception as btn_err:
                        print(f"[LocationSearcher] Error clicking search button: {btn_err}")
                
                # Wait for navigation and get final URL
                print(f"[LocationSearcher] Waiting for navigation...")
                logger.info("[STATUS] Waiting for page to redirect...")
                
                final_url = None
                max_wait_seconds = 10
                check_interval = 0.3
                max_checks = int(max_wait_seconds / check_interval)
                
                for check_attempt in range(max_checks):
                    time.sleep(check_interval)
                    try:
                        if page.is_closed():
                            print(f"[LocationSearcher] Page closed during URL polling")
                            break
                        
                        current_check_url = page.url
                        if current_check_url != initial_url and 'apartments.com' in current_check_url:
                            final_url = current_check_url
                            elapsed = (check_attempt + 1) * check_interval
                            print(f"[LocationSearcher] ✓ URL change detected after {elapsed:.1f}s! {initial_url} → {final_url}")
                            break
                        elif check_attempt == max_checks - 1:
                            print(f"[LocationSearcher] URL did not change after {max_wait_seconds}s. Still at: {current_check_url}")
                            final_url = current_check_url
                    except Exception as poll_err:
                        if 'closed' in str(poll_err).lower():
                            break
                        print(f"[LocationSearcher] Error checking URL: {poll_err}")
                
                # Get final URL
                if not final_url:
                    try:
                        if not page.is_closed():
                            final_url = page.url
                    except:
                        pass
                
                # Return URL if valid (all operations must be inside the 'with' block)
                if final_url and 'apartments.com' in final_url and final_url != 'https://www.apartments.com' and final_url != 'https://www.apartments.com/':
                    print(f"[LocationSearcher] ✓ Success! Returning URL: {final_url}")
                    return final_url
                
                print(f"[LocationSearcher] Could not find URL for {location_clean} on Apartments.com")
                return None
            
        except ImportError:
            print("[LocationSearcher] Playwright not installed - cannot use Browserless.io for Apartments.com")
            return None
        except Exception as e:
            print(f"[LocationSearcher] Playwright error for Apartments.com: {e}")
            import traceback
            print(f"[LocationSearcher] Traceback: {traceback.format_exc()}")
            return None
    
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
            
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
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
            
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
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
        """Search Zillow FSBO for a location using their search box.
        Element: <input placeholder="Address, neighborhood, city, ZIP" aria-label="Search" role="combobox">
        Result format: https://www.zillow.com/{city-state}/ (e.g., new-york-ny, los-angeles-ca)
        """
        driver = None
        try:
            location_clean = location.strip()
            logger.info(f"[LocationSearcher] Searching Zillow FSBO for: {location_clean}")
            
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
            # Go to Zillow homepage first (not FSBO page - search box is on homepage)
            driver.get("https://www.zillow.com")
            
            wait = WebDriverWait(driver, 20)
            # Wait for page to load
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(3)  # Additional wait for dynamic content
            except:
                time.sleep(5)  # Fallback wait
            
            print(f"[LocationSearcher] Looking for Zillow search box...")
            
            # Strategy 1: Find by exact placeholder and aria-label
            search_box = None
            try:
                search_box = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Address, neighborhood, city, ZIP']"))
                )
                # Verify it also has aria-label="Search"
                aria_label = search_box.get_attribute('aria-label') or ''
                if 'search' in aria_label.lower() or search_box.get_attribute('role') == 'combobox':
                    print(f"[LocationSearcher] ✓ Found Zillow search box by exact placeholder")
                    logger.info(f"[LocationSearcher] Found Zillow search box by exact placeholder")
                else:
                    search_box = None
            except TimeoutException:
                pass
            
            # Strategy 2: Find by placeholder pattern
            if not search_box:
                try:
                    search_box = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder*='Address, neighborhood' i]"))
                    )
                    print(f"[LocationSearcher] ✓ Found Zillow search box by placeholder pattern")
                    logger.info(f"[LocationSearcher] Found Zillow search box by placeholder pattern")
                except TimeoutException:
                    pass
            
            # Strategy 3: Find by role="combobox" and aria-label
            if not search_box:
                try:
                    search_box = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[role='combobox'][aria-label='Search']"))
                    )
                    print(f"[LocationSearcher] ✓ Found Zillow search box by role and aria-label")
                    logger.info(f"[LocationSearcher] Found Zillow search box by role and aria-label")
                except TimeoutException:
                    pass
            
            # Strategy 4: Find by placeholder text (like FSBO)
            if not search_box:
                try:
                    print(f"[LocationSearcher] Trying placeholder text search...")
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[role='combobox']")
                    for inp in all_inputs:
                        try:
                            if inp.is_displayed() and inp.is_enabled():
                                placeholder = (inp.get_attribute('placeholder') or '').lower()
                                aria_label = (inp.get_attribute('aria-label') or '').lower()
                                # Zillow placeholder: "Address, neighborhood, city, ZIP"
                                if any(keyword in placeholder for keyword in ['address', 'neighborhood', 'city', 'zip']):
                                    # Make sure it's not a filter (price, beds)
                                    if 'price' not in placeholder and 'bed' not in placeholder and 'bath' not in placeholder:
                                        search_box = inp
                                        print(f"[LocationSearcher] ✓ Found Zillow search box by placeholder keywords")
                                        logger.info(f"[LocationSearcher] Found Zillow search box by placeholder: {placeholder[:50]}...")
                                        break
                        except:
                            continue
                except Exception as e:
                    print(f"[LocationSearcher] Placeholder search failed: {e}")
            
            if not search_box:
                raise TimeoutException("Search box not found on Zillow")
            
            # Click to focus
            search_box.click()
            time.sleep(0.5)
            search_box.clear()
            time.sleep(0.5)
            
            print(f"[LocationSearcher] Typing location: {location_clean}")
            search_box.send_keys(location_clean)
            time.sleep(2.5)  # Wait for autocomplete
            
            # Try clicking first suggestion or pressing Enter
            search_submitted = False
            try:
                suggestions_wait = WebDriverWait(driver, 5)
                suggestions = suggestions_wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul[role='listbox'] li, div[role='option'], div[aria-label*='result' i]"))
                )
                if suggestions:
                    print(f"[LocationSearcher] Found {len(suggestions)} suggestions, clicking first one...")
                    suggestions[0].click()
                    search_submitted = True
                    time.sleep(3)
                    print(f"[LocationSearcher] ✓ Clicked first suggestion")
            except TimeoutException:
                print(f"[LocationSearcher] No suggestions found, pressing Enter...")
            
            if not search_submitted:
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)
            
            current_url = driver.current_url
            print(f"[LocationSearcher] Zillow FSBO final URL: {current_url}")
            logger.info(f"[LocationSearcher] Zillow FSBO final URL: {current_url}")
            
            # Verify we got a valid Zillow URL (format: https://www.zillow.com/{city-state}/)
            if 'zillow.com' in current_url:
                # URL should be in format: https://www.zillow.com/new-york-ny/ or https://www.zillow.com/los-angeles-ca/
                # Remove trailing slash if present for consistency
                if current_url.endswith('/') and current_url.count('/') > 4:
                    current_url = current_url.rstrip('/')
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
            
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
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
            
            # FSBO works fine without proxy (same as FSBO scraper - no heavy bot detection)
            # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
            # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
            # Use local Chrome without proxy (FSBO proved this works)
            driver = cls._get_driver(use_zyte_proxy=False)
            driver.get("https://www.forsalebyowner.com")
            
            wait = WebDriverWait(driver, 15)
            # Wait for page to load - wait for body element
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)  # Additional wait for dynamic content to render
            except:
                time.sleep(3)  # Fallback wait
            
            print(f"[LocationSearcher] Looking for FSBO search box...")
            # FSBO element: <input placeholder="Search our exclusive home inventory. Enter an address, neighborhood, or city">
            # Element is absolutely positioned, so we need to wait for it to be visible
            search_box = None
            
            # Primary: Wait for element with exact placeholder text (most reliable)
            try:
                search_box = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Search our exclusive home inventory. Enter an address, neighborhood, or city']"))
                )
                print(f"[LocationSearcher] ✓ Found FSBO search box by exact placeholder")
                logger.info(f"[LocationSearcher] Found FSBO search box by exact placeholder")
            except TimeoutException:
                # Fallback 1: Try partial placeholder match
                try:
                    search_box = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder*='Search our exclusive home inventory']"))
                    )
                    print(f"[LocationSearcher] ✓ Found FSBO search box by partial placeholder")
                    logger.info(f"[LocationSearcher] Found FSBO search box by partial placeholder")
                except TimeoutException:
                    # Fallback 2: Try finding by class that matches the absolute positioning
                    try:
                        search_box = wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[class*='absolute'][placeholder*='exclusive home']"))
                        )
                        print(f"[LocationSearcher] ✓ Found FSBO search box by class and placeholder")
                        logger.info(f"[LocationSearcher] Found FSBO search box by class and placeholder")
                    except TimeoutException:
                        # Fallback 3: Find any input with the placeholder keywords
                        try:
                            all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[placeholder]")
                            for inp in all_inputs:
                                try:
                                    placeholder = (inp.get_attribute('placeholder') or '').lower()
                                    if 'exclusive home' in placeholder or ('search our' in placeholder and 'address' in placeholder):
                                        if inp.is_displayed():
                                            search_box = inp
                                            print(f"[LocationSearcher] ✓ Found FSBO search box by placeholder keywords")
                                            logger.info(f"[LocationSearcher] Found FSBO search box by placeholder: {placeholder[:50]}...")
                                            break
                                except:
                                    continue
                        except Exception as e:
                            print(f"[LocationSearcher] Fallback 3 failed: {e}")
            
            if not search_box:
                raise TimeoutException("Search box not found on FSBO after trying all strategies")
            
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
