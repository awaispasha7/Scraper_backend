"""
Base utilities shared across all platform modules.
Contains driver creation and headless mode detection.
"""

import os
import sys
import subprocess
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)


def should_use_headless() -> bool:
    """
    Check if browser should run in headless mode.
    Can be toggled via HEADLESS_BROWSER environment variable.
    Default: True (headless)
    Set HEADLESS_BROWSER=false to see browser window.
    
    For Linux servers without XServer:
    - Option 1: Use xvfb-run (X Virtual Framebuffer) - see setup instructions
    - Option 2: Set DISPLAY=:99 and start xvfb manually
    - Option 3: Let it auto-detect and force headless
    
    For Windows/Mac:
    - Works directly with HEADLESS_BROWSER=false
    """
    # Check user preference first
    headless_env = os.getenv("HEADLESS_BROWSER", "true").lower()
    user_wants_headless = headless_env not in ["false", "0", "no", "off"]
    
    # If user explicitly wants headless, use it
    if user_wants_headless:
        return True
    
    # User wants non-headless - check if display is available
    # On Windows/Mac, GUI is available
    # On Linux, check DISPLAY environment variable or if xvfb is available
    has_display = False
    if sys.platform == "win32" or sys.platform == "darwin":
        has_display = True
        print(f"[LocationSearcher] ✓ GUI available on {sys.platform}")
    elif sys.platform.startswith("linux"):
        # On Linux, check if DISPLAY is set
        display = os.getenv("DISPLAY")
        if display:
            has_display = True
            print(f"[LocationSearcher] ✓ DISPLAY environment variable set: {display}")
        else:
            # Check if xvfb is installed (for virtual display)
            try:
                result = subprocess.run(
                    ["which", "xvfb-run"],
                    capture_output=True,
                    timeout=2
                )
                xvfb_available = result.returncode == 0
                
                if xvfb_available:
                    # xvfb is available - we can use it but need to set DISPLAY
                    print(f"[LocationSearcher] ⚠️ xvfb-run found but DISPLAY not set. Attempting to start virtual display...")
                    print(f"[LocationSearcher] 💡 To use non-headless on Linux server:")
                    print(f"[LocationSearcher]   1. Start xvfb: Xvfb :99 -screen 0 1920x1080x24 &")
                    print(f"[LocationSearcher]   2. Set DISPLAY: export DISPLAY=:99")
                    print(f"[LocationSearcher]   3. Or use xvfb-run wrapper script")
                    has_display = False  # Still need DISPLAY to be set
                else:
                    print(f"[LocationSearcher] ⚠️ xvfb-run not found. Install with: apt-get install xvfb")
                    has_display = False
            except Exception as e:
                print(f"[LocationSearcher] Could not check for xvfb: {e}")
                has_display = False
    
    # If no display available, force headless even if user requested non-headless
    if not has_display:
        print(f"[LocationSearcher] ⚠️ HEADLESS_BROWSER=false but no XServer/DISPLAY available. Forcing headless mode.")
        print(f"[LocationSearcher] Platform: {sys.platform}, DISPLAY: {os.getenv('DISPLAY', 'not set')}")
        return True
    
    # Display is available and user wants non-headless
    print(f"[LocationSearcher] ⚠️ Running in NON-HEADLESS mode (HEADLESS_BROWSER=false)")
    print(f"[LocationSearcher] Browser window will be visible (if running locally or with VNC)")
    return False


def get_driver(use_zyte_proxy: bool = True):
    """
    Create and return a Chrome WebDriver instance with optional Zyte proxy.
    Uses the same direct proxy configuration approach as the existing scrapers.
    
    Args:
        use_zyte_proxy: If True and ZYTE_API_KEY is available, use Zyte proxy.
                        If False or key not available, use local Chrome without proxy.
    """
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
    
    # Configure Chrome options for regular Selenium
    # Check environment variable for headless mode (default: headless)
    use_headless = should_use_headless()
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
        
        # Enhanced anti-detection: Remove all automation signals
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    // Remove webdriver property (critical)
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    delete navigator.__proto__.webdriver;
                    
                    // Override plugins to look more human
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Override permissions API
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // Mock chrome runtime (websites check for this)
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Override getParameter to hide automation
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) {
                            return 'Intel Inc.';
                        }
                        if (parameter === 37446) {
                            return 'Intel Iris OpenGL Engine';
                        }
                        return getParameter.call(this, parameter);
                    };
                '''
            })
        except Exception as e:
            logger.warning(f"Could not execute enhanced CDP commands: {e}")
        
        if zyte_api_key:
            print(f"[LocationSearcher] ✓ Chrome driver created with Zyte proxy")
        else:
            print(f"[LocationSearcher] ✓ Chrome driver created (no proxy)")
        
        return driver
    except Exception as e:
        logger.error(f"[LocationSearcher] Failed to initialize WebDriver: {e}")
        raise Exception(f"Could not initialize browser: {str(e)}. Please ensure Chrome/Chromium is installed.")

