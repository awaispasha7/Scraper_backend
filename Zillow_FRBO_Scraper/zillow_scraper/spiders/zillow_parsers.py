"""Parser utilities for extracting data from Zillow pages"""
import json
import logging

logger = logging.getLogger(__name__)


class ZillowJSONParser:
    """Handles JSON extraction from Zillow pages"""
    
    @staticmethod
    def extract_listings(response, zipcode):
        """
        Extract property listings from Zillow search page
        
        Args:
            response: Scrapy response object
            zipcode: ZIP code being scraped
            
        Returns:
            list: List of property listing dictionaries
        """
        try:
            # Extract JSON data from page
            json_text = response.css("#__NEXT_DATA__::text").get('')
            if not json_text:
                logger.warning(f"No #__NEXT_DATA__ found for ZIP: {zipcode}")
                return []
            
            json_data = json.loads(json_text)
            
            # Navigate to listings - try multiple paths
            props = json_data.get('props', {})
            page_props = props.get('pageProps', {})
            
            # Try different extraction methods
            homes_listing = []
            
            # Method 1: Try cat1 path (most common)
            search_page_state = page_props.get('searchPageState', {})
            if 'cat1' in search_page_state:
                cat1 = search_page_state.get('cat1', {})
                search_results = cat1.get('searchResults', {})
                homes_listing = search_results.get('listResults', [])
                logger.info(f"ZIP {zipcode}: Using cat1 path, found {len(homes_listing)} listings")
            
            # Method 2: Check pageProps.searchResults
            if not homes_listing and 'searchResults' in page_props:
                search_results = page_props.get('searchResults', {})
                homes_listing = search_results.get('listResults', [])
                logger.info(f"ZIP {zipcode}: Using pageProps.searchResults, found {len(homes_listing)} listings")
            
            logger.info(f"ZIP {zipcode}: Found {len(homes_listing)} listings total")
            
            # Log structure if no listings found (for debugging)
            if len(homes_listing) == 0:
                logger.warning(f"ZIP {zipcode}: No listings found!")
                logger.debug(f"ZIP {zipcode}: pageProps keys: {list(page_props.keys())[:10]}")
                logger.debug(f"ZIP {zipcode}: searchPageState keys: {list(search_page_state.keys())[:10]}")
            
            return homes_listing
            
        except json.JSONDecodeError as e:
            logger.error(f"ZIP {zipcode}: JSON decode error: {e}")
            return []
        except Exception as e:
            logger.error(f"ZIP {zipcode}: Error extracting listings: {e}", exc_info=True)
            return []
    
    @staticmethod
    def extract_property_details(response):
        """
        Extract property details from detail page
        
        Args:
            response: Scrapy response object
            
        Returns:
            dict: Property details including address, price, beds/baths, etc.
        """
        item = {}
        item['Url'] = response.url
        
        try:
            json_data = json.loads(response.css("#__NEXT_DATA__::text").get(''))
            detail = json_data.get('props', {}).get('pageProps', {}).get('componentProps')
            home_detail = detail.get('gdpClientCache', '')
            
            if home_detail:
                home_data = json.loads(home_detail)
                detail_key = list(home_data.keys())[0]
                home = home_data.get(detail_key, {}).get('property', '')
            else:
                home = detail.get('initialReduxState', {}).get('gdp', {}).get('building', {})
            
            detail1 = json_data.get('props', {}).get('pageProps', {}).get('componentProps', {})
            zpid = (
                detail1.get('initialReduxState', {})
                .get('gdp', {})
                .get('building', {})
                .get('zpid', '')
            )

            if not zpid:
                zpid = detail1.get('zpid', '')
            
            # Extract property information
            item['Days On Zillow'] = home.get('daysOnZillow', '')
            
            # Extract address
            # Try JSON first (more reliable)
            street = home.get('streetAddress')
            city = home.get('city')
            state = home.get('state')
            zip_code = home.get('zipcode')
            
            if street and city and state:
                item["Address"] = f"{street}, {city}, {state} {zip_code or ''}".strip()
            else:
                # Fallback to XPath
                try:
                    address = "".join([text.strip() for text in response.xpath(
                        '//*[@data-test-id="bdp-building-address"]//text() |//div[contains(@class,"styles__AddressWrapper")]/h1//text()').getall()]).strip()
                    item["Address"] = address.replace(',', ', ')
                except:
                    try:
                        address = "".join([text.strip() for text in response.xpath(
                            '//div[contains(@class,"styles__AddressWrapper")]/h1//text()').getall()]).strip()
                        item["Address"] = address.replace(',', ', ')
                    except:
                        item["Address"] = ""
            
            # Extract beds and baths
            beds = home.get('bedrooms')
            baths = home.get('bathrooms')

            beds_bath = ""
            if beds and baths:
                beds_bath = f"{beds} Beds {baths} Baths"
            elif beds:
                beds_bath = f"{beds} Beds"
            elif baths:
                beds_bath = f"{baths} Baths"
            else:
                beds_bath = ""

            # Extract price from JSON
            price = home.get('price')
            if not price:
                price = home.get('monthlyRent')
            
            # Check for units if price is still missing
            if not price:
                units = home.get('units')
                if units and isinstance(units, list):
                    prices = [u.get('price') for u in units if u.get('price')]
                    if not prices: # Try getting price from string format in units
                         prices = []
                         for u in units:
                             p = u.get('price')
                             if not p: continue
                             if isinstance(p, str):
                                 p = p.replace('$','').replace(',','').replace('+','')
                                 try: prices.append(float(p))
                                 except: pass
                             elif isinstance(p, (int, float)):
                                 prices.append(p)
                    
                    if prices:
                        min_p = min(prices)
                        max_p = max(prices)
                        if min_p == max_p:
                            price = min_p
                        else:
                            price = f"${min_p:,} - ${max_p:,}"

            if price:
                if isinstance(price, (int, float)):
                    item['Asking Price'] = f"${price:,}"
                else:
                    item['Asking Price'] = str(price)
            else:
                # Fallback to XPath
                item['Asking Price'] = response.xpath('//span[@data-testid="price"]//span//text()').get('').strip()
            item['YearBuilt'] = home.get('yearBuilt', '')
            
            return item, zpid, beds_bath
            
        except Exception as e:
            logger.error(f"Error extracting property details: {e}", exc_info=True)
            return item, None, ""
    
    @staticmethod
    def build_agent_payload(zpid):
        """
        Build payload for agent info API request
        
        Args:
            zpid: Zillow Property ID
            
        Returns:
            dict: Payload for API request
        """
        return {
            'zpid': f'{zpid}',
            'pageType': 'HDP',
            'isInstantTourEnabled': False,
            'isCachedInstantTourAvailability': True,
            'tourTypes': [],
        }
