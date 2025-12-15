import json
import scrapy
from ..items import ZillowScraperItem
from ..zillow_config import HEADERS, BASE_URL

class ZillowSpiderSpider(scrapy.Spider):
    name = "zillow_spider"
    unique_list = []

    def start_requests(self):
        """Initial request to Zillow FSBO listings"""
        # Use provided URL via -a start_url if available, else usage default
        start_url = getattr(self, 'start_url', None)
        if not start_url:
            # Default filtered URL
            start_url = "https://www.zillow.com/homes/for_sale/?searchQueryState=%7B%22pagination%22%3A%7B%7D%2C%22isMapVisible%22%3Atrue%2C%22mapBounds%22%3A%7B%22west%22%3A-88.80532949149847%2C%22east%22%3A-87.34964101493597%2C%22south%22%3A41.273733987949605%2C%22north%22%3A42.289555725011496%7D%2C%22mapZoom%22%3A9%2C%22usersSearchTerm%22%3A%22%22%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22globalrelevanceex%22%7D%2C%22price%22%3A%7B%22min%22%3Anull%2C%22max%22%3A350000%7D%2C%22mp%22%3A%7B%22min%22%3Anull%2C%22max%22%3A1799%7D%2C%22tow%22%3A%7B%22value%22%3Afalse%7D%2C%22mf%22%3A%7B%22value%22%3Afalse%7D%2C%22con%22%3A%7B%22value%22%3Afalse%7D%2C%22land%22%3A%7B%22value%22%3Afalse%7D%2C%22apa%22%3A%7B%22value%22%3Afalse%7D%2C%22manu%22%3A%7B%22value%22%3Afalse%7D%2C%22apco%22%3A%7B%22value%22%3Afalse%7D%2C%22fsba%22%3A%7B%22value%22%3Afalse%7D%2C%22nc%22%3A%7B%22value%22%3Afalse%7D%2C%22fore%22%3A%7B%22value%22%3Afalse%7D%2C%22auc%22%3A%7B%22value%22%3Afalse%7D%7D%2C%22isListVisible%22%3Atrue%7D"
        
        self.logger.info(f"Starting scrape for: {start_url}")
        yield scrapy.Request(
            url=start_url, 
            callback=self.parse,
            meta={
                "zyte_api": {
                    "browserHtml": True,
                    "geolocation": "US"
                }
            }
        )

    def parse(self, response):
        """Parse search results page"""
        try:
            data = response.css("#__NEXT_DATA__::text").get('')
            if not data:
                self.logger.warning(f"No NEXT_DATA found on {response.url}")
                return

            json_data = json.loads(data)
            homes_listing = json_data.get('props', {}).get('pageProps', {}).get('searchPageState', {}).get('cat1', {}).get(
                'searchResults', {}).get('listResults', []) or json_data.get('props', {}).get('pageProps', {}).get('searchPageState', {}).get('cat2', {}).get(
                'searchResults', {}).get('listResults', [])
            
            if not homes_listing:
                self.logger.warning(f"No listings found on {response.url}")
                return
                
            self.logger.info(f"Found {len(homes_listing)} listings on page")
            
            for home in homes_listing[:]:
                url = home.get('detailUrl', '')
                new_detailUrl = ''
                if not url.startswith("https"):
                    new_detailUrl = f'{BASE_URL}{url}'
                else:
                    new_detailUrl = url
                yield response.follow(
                    url=new_detailUrl, 
                    callback=self.detail_page,
                    dont_filter=True, 
                    meta={
                        'new_detailUrl': new_detailUrl,
                        "zyte_api": {
                            "browserHtml": True,
                            "geolocation": "US"
                        }
                    }
                )
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in parse: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in parse: {e}", exc_info=True)

        next_page = response.xpath("//a[@title='Next page']/@href").get('')
        if next_page:
            self.logger.info(f"Found next page: {next_page}")
            yield scrapy.Request(
                response.urljoin(next_page), 
                callback=self.parse,
                meta={
                    "zyte_api": {
                        "browserHtml": True,
                        "geolocation": "US"
                    }
                }
            )

    def detail_page(self, response):
        """Parse property detail page"""
        try:
            item = ZillowScraperItem()
            item['Detail_URL'] = response.url
            
            data = response.css("#__NEXT_DATA__::text").get('')
            if not data:
                self.logger.warning(f"No NEXT_DATA found on detail page {response.url}")
                return

            json_data = json.loads(data)
            detail = json_data.get('props', {}).get('pageProps', {}).get('componentProps')
            home_detail = detail.get('gdpClientCache', '')
            
            if home_detail:
                home_data = json.loads(home_detail)
                detail_key = list(home_data.keys())[0]
                home = home_data.get(detail_key, {}).get('property', '')
            else:
                home = detail.get('initialReduxState', {}).get('gdp', {}).get('building', {})
            
            detail1 = json_data.get('props', {}).get('pageProps', {}).get('componentProps', {})
            zpid = (detail1.get('initialReduxState', {}).get('gdp', {}).get('building', {}).get('zpid', ''))
            if not zpid:
                zpid = detail1.get('zpid', '')
            
            # Extract address with improved error handling
            try:
                raw_address = "".join([text.strip() for text in response.xpath('//*[@data-test-id="bdp-building-address"]//text() |//div[contains(@class,"styles__AddressWrapper")]/h1//text()').getall()]).strip()
                # Normalize whitespace (replace multiple spaces with single space)
                address = " ".join(raw_address.split())
                
                # Strict Filtering: Skip if not in Illinois
                if "IL" not in address and "Illinois" not in address:
                    self.logger.info(f"⛔ Skipping non-IL listing: {address}")
                    return
                
                item["Address"] = address
            except Exception as e:
                self.logger.warning(f"Error extracting primary address: {e}")
                try:
                    raw_address = "".join([text.strip() for text in response.xpath('//div[contains(@class,"styles__AddressWrapper")]/h1//text()').getall()]).strip()
                    address = " ".join(raw_address.split())
                    if "IL" not in address and "Illinois" not in address:
                        return
                    item["Address"] = address
                except Exception as e2:
                    self.logger.warning(f"Error extracting fallback address: {e2}")
                    item["Address"] = ""

            item['Bedrooms'] = home.get('bedrooms', '')
            item['Bathrooms'] = home.get('bathrooms', '')
            item['Price'] = response.xpath('//span[@data-testid="price"]//span//text()').get('').strip()
            item['Home_Type'] = home.get('homeType', '').replace('_', ' ').replace('HOME_TYPE', '').strip()
            item['Year_Build'] = response.xpath("//span[contains(text(),'Built in')]//text()").get('').strip()
            item['HOA'] = response.xpath("//span[contains(text(),'HOA')]//text()").get('').strip()
            item['Days_On_Zillow'] = home.get('daysOnZillow', '')
            item['Page_View_Count'] = home.get('pageViewCount', '')
            item['Favorite_Count'] = home.get('favoriteCount', '')
            
            # Extract phone number with improved error handling
            listed = home.get('listedBy', [])
            if listed:
                for b in listed:
                    owner = b.get('id')
                    if owner == 'PROPERTY_OWNER':
                        elements = b.get('elements')
                        if elements:
                            for phone in elements:
                                phone_id = phone.get('id')
                                if phone_id == 'PHONE':
                                    item['Phone_Number'] = phone.get('text', '')
                                    break
            
            if item['Detail_URL'] not in self.unique_list:
                self.unique_list.append(item['Detail_URL'])
                self.logger.info(f"✓ Scraped: {item.get('Address', 'N/A')} | Price: {item.get('Price', 'N/A')}")
                yield item
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in detail_page for {response.url}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in detail_page for {response.url}: {e}", exc_info=True)