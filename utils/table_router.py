"""
Table Router

Maps detected platforms to their corresponding database tables and scraper configurations.
"""

from typing import Optional, Dict, Tuple
from utils.url_detector import URLDetector


class TableRouter:
    """Routes platforms to database tables and scraper configurations."""
    
    # Platform to table mapping
    PLATFORM_TO_TABLE = {
        'apartments.com': 'apartments_frbo',
        'hotpads': 'hotpads_listings',
        'redfin': 'redfin_listings',
        'trulia': 'trulia_listings',
        'zillow_fsbo': 'zillow_fsbo_listings',
        'zillow_frbo': 'zillow_frbo_listings',
        'fsbo': 'listings',
    }
    
    # Platform to scraper configuration
    PLATFORM_TO_SCRAPER = {
        'apartments.com': {
            'scraper_name': 'apartments_frbo',
            'scraper_dir': 'Apartments_Scraper',
            'url_param': 'url',
            'command': ['-m', 'scrapy', 'crawl', 'apartments_frbo', '-a'],
        },
        'hotpads': {
            'scraper_name': 'hotpads_scraper',
            'scraper_dir': 'Hotpads_Scraper',
            'url_param': 'url',
            'command': ['-m', 'scrapy', 'crawl', 'hotpads_scraper', '-a'],
        },
        'redfin': {
            'scraper_name': 'redfin_spider',
            'scraper_dir': 'Redfin_Scraper',
            'url_param': 'start_url',
            'command': ['-m', 'scrapy', 'crawl', 'redfin_spider', '-a'],
        },
        'trulia': {
            'scraper_name': 'trulia_spider',
            'scraper_dir': 'Trulia_Scraper',
            'url_param': 'url',
            'command': ['-m', 'scrapy', 'crawl', 'trulia_spider', '-a'],
        },
        'zillow_fsbo': {
            'scraper_name': 'zillow_spider',
            'scraper_dir': 'Zillow_FSBO_Scraper',
            'url_param': 'start_url',
            'command': ['-m', 'scrapy', 'crawl', 'zillow_spider', '-a'],
        },
        'zillow_frbo': {
            'scraper_name': 'zillow_spider',
            'scraper_dir': 'Zillow_FRBO_Scraper',
            'url_param': 'url',
            'command': ['-m', 'scrapy', 'crawl', 'zillow_spider', '-a'],
        },
        'fsbo': {
            'scraper_name': 'forsalebyowner_selenium_scraper',
            'scraper_dir': 'FSBO_Scraper',
            'url_param': 'base_url',
            'command': ['forsalebyowner_selenium_scraper.py'],
        },
    }
    
    @classmethod
    def get_table_for_platform(cls, platform: Optional[str]) -> Optional[str]:
        """
        Get the database table name for a platform.
        
        Args:
            platform: Platform identifier
            
        Returns:
            Table name or None if unknown platform
        """
        if not platform:
            return None
        return cls.PLATFORM_TO_TABLE.get(platform)
    
    @classmethod
    def get_scraper_config(cls, platform: Optional[str]) -> Optional[Dict]:
        """
        Get scraper configuration for a platform.
        
        Args:
            platform: Platform identifier
            
        Returns:
            Scraper configuration dict or None if unknown platform
        """
        if not platform:
            return None
        return cls.PLATFORM_TO_SCRAPER.get(platform)
    
    @classmethod
    def route_url(cls, url: str) -> Tuple[Optional[str], Optional[str], Optional[Dict], Dict]:
        """
        Route a URL to the appropriate table and scraper configuration.
        
        Args:
            url: The URL to route
            
        Returns:
            Tuple of (platform, table_name, scraper_config, location_dict)
            Returns None values for unknown platforms
        """
        platform, location = URLDetector.detect_and_extract(url)
        
        if not platform:
            return None, None, None, location
        
        table_name = cls.get_table_for_platform(platform)
        scraper_config = cls.get_scraper_config(platform)
        
        return platform, table_name, scraper_config, location
    
    @classmethod
    def is_supported_platform(cls, platform: Optional[str]) -> bool:
        """
        Check if a platform is supported.
        
        Args:
            platform: Platform identifier
            
        Returns:
            True if platform is supported, False otherwise
        """
        if not platform:
            return False
        return platform in cls.PLATFORM_TO_TABLE

