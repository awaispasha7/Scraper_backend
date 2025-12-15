# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class ApartmentsSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ApartmentsDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ZyteApiDownloaderMiddleware:
    """
    Downloader middleware that uses Zyte API to fetch pages.
    This bypasses bot detection by using Zyte's browser automation.
    """
    ZYTE_API_URL = "https://api.zyte.com/v1/extract"
    
    def __init__(self, zyte_api_key):
        self.zyte_api_key = zyte_api_key
        import requests
        self.requests = requests
    
    @classmethod
    def from_crawler(cls, crawler):
        import os
        from pathlib import Path
        
        # Try to get API key from settings first
        api_key = crawler.settings.get("ZYTE_API_KEY")
        
        # If not in settings, try to load from Scraper_backend root .env first
        if not api_key:
            # middlewares.py -> apartments_scraper -> Apartments_Scraper -> Scraper_backend
            project_root = Path(__file__).resolve().parents[2]  # Go up to Scraper_backend
            env_path = project_root / '.env'
            if env_path.exists():
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("ZYTE_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break
                except Exception as e:
                    pass  # Will try other methods
        
        # If not in root .env, try environment variable
        if not api_key:
            api_key = os.getenv("ZYTE_API_KEY")
        
        # Fallback: try reading from apartments_scraper/.env
        if not api_key:
            package_dir = os.path.dirname(os.path.abspath(__file__))
            env_path = os.path.join(package_dir, ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("ZYTE_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                break
                except Exception as e:
                    pass
        
        if not api_key:
            raise ValueError("ZYTE_API_KEY not found in settings, environment, or .env file")
        
        return cls(zyte_api_key=api_key)
    
    def process_exception(self, request, exception, spider):
        """
        Handle exceptions raised by this middleware.
        For 520 errors, return None to let Scrapy call the error handler.
        """
        # Check if this is a 520 error exception from our middleware
        if "520" in str(exception) or "Website Ban" in str(exception):
            spider.logger.info(f"🔄 Caught 520 exception in process_exception - returning None to trigger error handler")
            # Return None to let Scrapy's error handling call the error handler (errback)
            # This will allow the spider's handle_error method to skip to the next page
            return None
        
        # For other exceptions, return None to let Scrapy handle normally
        return None
    
    def process_request(self, request, spider):
        """
        Intercept the request and fetch using Zyte API instead.
        """
        import time
        from scrapy.http import HtmlResponse
        from scrapy.utils.python import to_bytes
        
        spider.logger.debug(f"Fetching {request.url} via Zyte API")
        
        # Fetch via Zyte API with browser rendering (required for JavaScript-heavy sites)
        # Note: Cannot use both browserHtml and httpResponseBody in same request
        payload = {
            "url": request.url,
            "browserHtml": True,  # Use browser rendering to bypass bot detection
        }
        
        # Use fewer retries for 520 errors (Website Ban) - they're usually persistent
        # Use full retries for other transient errors
        max_retries = 5  # Default for transient errors
        max_retries_520 = 2  # Only 2 attempts for 520 errors (faster skipping)
        last_error = None
        last_status_code = None
        is_520_detected = False
        
        for attempt in range(max_retries):
            try:
                # Add random delay before each request to appear more human-like
                if attempt > 0:
                    import random
                    pre_delay = random.uniform(1.0, 2.0)  # Reduced from 2-5s to 1-2s for faster retries
                    spider.logger.info(f"⏳ Waiting {pre_delay:.1f}s before retry attempt {attempt + 1}/{max_retries}")
                    time.sleep(pre_delay)
                else:
                    spider.logger.info(f"🔄 Attempt {attempt + 1}/{max_retries} for {request.url}")
                
                resp = self.requests.post(
                    self.ZYTE_API_URL,
                    json=payload,
                    auth=(self.zyte_api_key, ""),
                    timeout=90,  # Increased to 90s to allow more time for anti-ban measures
                    headers={"Content-Type": "application/json"},
                )
                
                last_status_code = resp.status_code
                
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError as e:
                        # Handle JSON decode errors
                        spider.logger.error(
                            f"Failed to decode JSON response from Zyte API for {request.url}: {e}. "
                            f"Response text: {resp.text[:500]}"
                        )
                        if attempt < max_retries - 1:
                            wait = 2 * (attempt + 1)
                            spider.logger.warning(
                                f"Retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                            )
                            time.sleep(wait)
                            continue
                        break
                    
                    html = data.get("browserHtml") or ""
                    
                    if html:
                        # Create a Scrapy Response object
                        return HtmlResponse(
                            url=request.url,
                            body=to_bytes(html),
                            encoding="utf-8",
                            request=request,
                        )
                    else:
                        spider.logger.warning(f"Empty HTML from Zyte for {request.url}")
                
                elif resp.status_code == 520:
                    # 520 (Website Ban) - usually persistent, use fewer retries for faster skipping
                    is_520_detected = True
                    last_error = f"HTTP {resp.status_code}"
                    
                    # Try to get error details from response
                    error_details = ""
                    try:
                        error_text = resp.text[:300] if resp.text else "No response body"
                        error_details = f" - {error_text}"
                    except:
                        error_details = " - Could not read response"
                    
                    # For 520 errors, only retry once (2 total attempts)
                    if attempt < max_retries_520 - 1:
                        # Quick retry for 520 - don't wait too long
                        wait = 3  # Short wait for 520 errors
                        spider.logger.warning(
                            f"⚠️ Zyte API error 520 (Website Ban) for {request.url}{error_details}, "
                            f"retrying in {wait}s (attempt {attempt + 1}/{max_retries_520})"
                        )
                        time.sleep(wait)
                        continue
                    else:
                        # Last attempt failed - will trigger error handler for automatic skip
                        spider.logger.error(
                            f"❌ Zyte API error 520 (Website Ban) for {request.url}{error_details} - all retries exhausted. Will skip to next page."
                        )
                        # Break out of loop early for 520 errors
                        break
                
                elif resp.status_code in (522, 524, 500, 502, 503, 504):
                    # Other transient errors - use full retries
                    last_error = f"HTTP {resp.status_code}"
                    
                    # Try to get error details from response
                    error_details = ""
                    try:
                        error_text = resp.text[:300] if resp.text else "No response body"
                        error_details = f" - {error_text}"
                    except:
                        error_details = " - Could not read response"
                    
                    if attempt < max_retries - 1:
                        # Reduced exponential backoff: 3s, 5s, 8s, 10s, 15s (faster recovery)
                        wait_times = [3, 5, 8, 10, 15]  # Reduced from [5, 10, 15, 20, 30]
                        wait = wait_times[min(attempt, len(wait_times) - 1)]
                        
                        spider.logger.warning(
                            f"⚠️ Zyte API error {resp.status_code} for {request.url}{error_details}, "
                            f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait)
                        continue
                    else:
                        # Last attempt failed
                        spider.logger.error(
                            f"❌ Zyte API error {resp.status_code} for {request.url}{error_details} - all retries exhausted"
                        )
                
                elif resp.status_code in (401, 403, 402, 429, 422):
                    # Auth/quota/rate limit - don't retry
                    last_error = f"HTTP {resp.status_code} (Auth/Quota/Rate Limit)"
                    error_text = ""
                    try:
                        error_text = resp.text[:300] if resp.text else "No response body"
                    except:
                        error_text = "Could not read response"
                    
                    spider.logger.error(
                        f"❌ Zyte API error {resp.status_code} for {request.url}: {error_text} - Stopping retries"
                    )
                    break
                
                else:
                    # Unknown status code
                    last_error = f"HTTP {resp.status_code} (Unknown)"
                    error_text = ""
                    try:
                        error_text = resp.text[:300] if resp.text else "No response body"
                    except:
                        error_text = "Could not read response"
                    
                    spider.logger.warning(
                        f"⚠️ Zyte API returned unknown status {resp.status_code} for {request.url}: {error_text}"
                    )
                    if attempt < max_retries - 1:
                        wait = 5 * (attempt + 1)
                        spider.logger.info(f"Retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                        continue
                
            except self.requests.exceptions.Timeout:
                last_error = "Request Timeout"
                if attempt < max_retries - 1:
                    # Reduced exponential backoff for timeouts: 3s, 5s, 8s, 10s, 15s
                    wait_times = [3, 5, 8, 10, 15]  # Reduced from [5, 10, 15, 20, 30]
                    wait = wait_times[min(attempt, len(wait_times) - 1)]
                    spider.logger.warning(
                        f"⏱️ Zyte API timeout for {request.url}, "
                        f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
                    continue
                else:
                    spider.logger.error(f"❌ Zyte API timeout for {request.url} - all retries exhausted")
            
            except self.requests.exceptions.RequestException as e:
                last_error = f"Request Exception: {str(e)}"
                spider.logger.error(f"❌ Zyte API request exception for {request.url}: {e}")
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    spider.logger.info(f"Retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
            
            except Exception as e:
                last_error = f"Exception: {type(e).__name__}: {str(e)}"
                spider.logger.error(f"❌ Zyte API unexpected error for {request.url}: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    spider.logger.info(f"Retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
        
        # If all retries failed, handle based on error type
        error_summary = f"Status: {last_status_code}" if last_status_code else f"Error: {last_error}" if last_error else "Unknown error"
        spider.logger.error(f"❌ All Zyte API attempts failed for {request.url} - {error_summary}")
        
        # For 520 errors (Website Ban), raise an exception that will be caught by process_exception
        # process_exception will return None to let Scrapy call the error handler
        if is_520_detected:
            # Raise a custom exception that process_exception will catch
            spider.logger.info(f"🔄 Raising exception for 520 error - will be caught by process_exception")
            raise Exception(f"Zyte API error 520 (Website Ban) for {request.url}")
        
        # For other errors, return None to let Scrapy's retry middleware handle it
        return None