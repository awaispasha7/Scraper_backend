"""
FSBO (ForSaleByOwner.com) platform search module.
Isolated from other platforms to prevent cascading failures.
"""

import time
import logging
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .base import get_driver

logger = logging.getLogger(__name__)


def search_fsbo(location: str) -> Optional[str]:
    """Search ForSaleByOwner.com for a location using their search box."""
    driver = None
    try:
        location_clean = location.strip()
        logger.info(f"[FSBO] Searching FSBO for: {location_clean}")
        
        # FSBO works fine without proxy (same as FSBO scraper - no heavy bot detection)
        # Main scrapers use scrapy-zyte-api (HTTP API), not Selenium proxy
        # Zyte proxy via --proxy-server doesn't work well with Selenium interactive automation
        # Use local Chrome without proxy (FSBO proved this works)
        driver = get_driver(use_zyte_proxy=False)
        driver.get("https://www.forsalebyowner.com")
        
        wait = WebDriverWait(driver, 15)
        # Wait for page to load - wait for body element
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # Additional wait for dynamic content to render
        except:
            time.sleep(3)  # Fallback wait
        
        print(f"[FSBO] Looking for FSBO search box...")
        # FSBO element: <input placeholder="Search our exclusive home inventory. Enter an address, neighborhood, or city">
        # Element is absolutely positioned, so we need to wait for it to be visible
        search_box = None
        
        # Primary: Wait for element with exact placeholder text (most reliable)
        try:
            search_box = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Search our exclusive home inventory. Enter an address, neighborhood, or city']"))
            )
            print(f"[FSBO] ✓ Found FSBO search box by exact placeholder")
            logger.info(f"[FSBO] Found FSBO search box by exact placeholder")
        except TimeoutException:
            # Fallback 1: Try partial placeholder match
            try:
                search_box = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder*='Search our exclusive home inventory']"))
                )
                print(f"[FSBO] ✓ Found FSBO search box by partial placeholder")
                logger.info(f"[FSBO] Found FSBO search box by partial placeholder")
            except TimeoutException:
                # Fallback 2: Try finding by class that matches the absolute positioning
                try:
                    search_box = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[class*='absolute'][placeholder*='exclusive home']"))
                    )
                    print(f"[FSBO] ✓ Found FSBO search box by class and placeholder")
                    logger.info(f"[FSBO] Found FSBO search box by class and placeholder")
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
                                        print(f"[FSBO] ✓ Found FSBO search box by placeholder keywords")
                                        logger.info(f"[FSBO] Found FSBO search box by placeholder: {placeholder[:50]}...")
                                        break
                            except:
                                continue
                    except Exception as e:
                        print(f"[FSBO] Fallback 3 failed: {e}")
        
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
        logger.info(f"[FSBO] FSBO final URL: {current_url}")
        
        if 'forsalebyowner.com' in current_url:
            return current_url
        
        return None
        
    except TimeoutException:
        logger.error(f"[FSBO] Timeout waiting for FSBO search box")
        return None
    except Exception as e:
        logger.error(f"[FSBO] Error searching FSBO: {e}")
        return None
    finally:
        if driver:
            driver.quit()

