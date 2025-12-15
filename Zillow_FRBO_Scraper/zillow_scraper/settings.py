# Scrapy settings for zillow_scraper project
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from project root (Scraper_backend/.env)
project_root = Path(__file__).resolve().parents[2]  # Go up to Scraper_backend
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

BOT_NAME = "zillow_scraper"

SPIDER_MODULES = ["zillow_scraper.spiders"]
NEWSPIDER_MODULE = "zillow_scraper.spiders"

ROBOTSTXT_OBEY = False

CONCURRENT_REQUESTS = 32
DOWNLOAD_DELAY = 0.1
CONCURRENT_REQUESTS_PER_DOMAIN = 32

ITEM_PIPELINES = {
    'zillow_scraper.pipelines.supabase_pipeline.SupabasePipeline': 400,
}

FEED_EXPORT_ENCODING = "utf-8"

# ==================== Zyte API Configuration ====================
ZYTE_API_KEY = os.getenv('ZYTE_API_KEY')
# ZYTE_API_TRANSPARENT_MODE = True

DOWNLOAD_HANDLERS = {
    "http": "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
    "https": "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
}

DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware": 1000,
}

REQUEST_FINGERPRINTER_CLASS = "scrapy_zyte_api.ScrapyZyteAPIRequestFingerprinter"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
