import os

# ==================== API Configuration ====================
ZYTE_API_KEY = os.getenv('ZYTE_API_KEY', '')
# Correct proxy format for Zyte API
ZYTE_PROXY = f'http://{ZYTE_API_KEY}:@api.zyte.com:8011' if ZYTE_API_KEY else None

# ==================== Spider Settings ====================
ROBOTSTXT_OBEY = False
RETRY_TIMES = 5
DOWNLOAD_DELAY = 0.1
CONCURRENT_REQUESTS = 16

# ==================== HTTP Headers ====================
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

# ==================== Output Configuration ====================
OUTPUT_FIELDS = [
    'Detail_URL',
    'Address',
    'Bedrooms',
    'Bathrooms',
    'Price',
    'Home_Type',
    'Year_Build',
    'HOA',
    'Days_On_Zillow',
    'Page_View_Count',
    'Favorite_Count',
    'Phone_Number',
]

# ==================== URL Constants ====================
BASE_URL = 'https://www.zillow.com'
