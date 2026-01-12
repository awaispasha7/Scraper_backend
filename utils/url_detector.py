"""
URL Detector and Platform Identifier

This module detects the platform from a URL and extracts location information.
"""

import re
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse, parse_qs


class URLDetector:
    """Detects platform and extracts location information from URLs."""
    
    # Platform patterns
    PLATFORM_PATTERNS = {
        'apartments.com': {
            'domains': ['apartments.com', 'www.apartments.com'],
            'pattern': r'apartments\.com',
            'location_pattern': r'/([a-z0-9-]+(?:-[a-z]{2})?)/',
        },
        'hotpads': {
            'domains': ['hotpads.com', 'www.hotpads.com'],
            'pattern': r'hotpads\.com',
            'location_pattern': r'/([a-z0-9-]+)/',
        },
        'redfin': {
            'domains': ['redfin.com', 'www.redfin.com'],
            'pattern': r'redfin\.com',
            'location_pattern': r'/([A-Z]{2})/([A-Za-z0-9-]+)',
        },
        'trulia': {
            'domains': ['trulia.com', 'www.trulia.com'],
            'pattern': r'trulia\.com',
            'location_pattern': r'/([A-Z]{2})/([A-Za-z0-9-]+)',
        },
        'zillow_fsbo': {
            'domains': ['zillow.com', 'www.zillow.com'],
            'pattern': r'zillow\.com.*for.*sale',
            'location_pattern': r'/([A-Z]{2})/([A-Za-z0-9-]+)',
        },
        'zillow_frbo': {
            'domains': ['zillow.com', 'www.zillow.com'],
            'pattern': r'zillow\.com.*for.*rent',
            'location_pattern': r'/([A-Z]{2})/([A-Za-z0-9-]+)',
        },
        'fsbo': {
            'domains': ['forsalebyowner.com', 'www.forsalebyowner.com'],
            'pattern': r'forsalebyowner\.com',
            'location_pattern': r'/([A-Z]{2})/([A-Za-z0-9-]+)',
        },
    }
    
    # State abbreviations for validation
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }
    
    @classmethod
    def detect_platform(cls, url: str) -> Optional[str]:
        """
        Detect the platform from a URL.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Platform identifier or None if unknown
        """
        if not url:
            return None
            
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        domain = parsed.netloc.replace('www.', '')
        
        # Check each platform pattern
        for platform, config in cls.PLATFORM_PATTERNS.items():
            # Check domain match
            if domain in config['domains']:
                # For Zillow, check if it's FSBO or FRBO based on URL pattern
                if platform.startswith('zillow_'):
                    # Check for rentals/FRBO patterns first (more specific)
                    # Accept both /rentals/ and /for_rent/ or /for-rent/ patterns
                    if '/rentals/' in url_lower or '/for_rent/' in url_lower or '/for-rent/' in url_lower or 'for_rent' in url_lower or 'for-rent' in url_lower or 'frbo' in url_lower:
                        return 'zillow_frbo'
                    elif '/fsbo/' in url_lower or '/for_sale/' in url_lower or '/for-sale/' in url_lower or 'for_sale' in url_lower or 'for-sale' in url_lower or 'fsbo' in url_lower:
                        return 'zillow_fsbo'
                    # Default to FSBO if unclear
                    return 'zillow_fsbo'
                return platform
            
            # Check pattern match as fallback
            if re.search(config['pattern'], url_lower):
                if platform.startswith('zillow_'):
                    # Check for rentals/FRBO patterns first (more specific)
                    # Accept both /rentals/ and /for_rent/ or /for-rent/ patterns
                    if '/rentals/' in url_lower or '/for_rent/' in url_lower or '/for-rent/' in url_lower or 'for_rent' in url_lower or 'for-rent' in url_lower or 'frbo' in url_lower:
                        return 'zillow_frbo'
                    elif '/fsbo/' in url_lower or '/for_sale/' in url_lower or '/for-sale/' in url_lower or 'for_sale' in url_lower or 'for-sale' in url_lower or 'fsbo' in url_lower:
                        return 'zillow_fsbo'
                    return 'zillow_fsbo'
                return platform
        
        return None
    
    @classmethod
    def extract_location(cls, url: str, platform: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extract location information (city, state) from URL.
        
        Args:
            url: The URL to analyze
            platform: Optional platform identifier (will be detected if not provided)
            
        Returns:
            Dictionary with 'city' and 'state' keys (values may be None)
        """
        location = {'city': None, 'state': None}
        
        if not url:
            return location
        
        if not platform:
            platform = cls.detect_platform(url)
        
        if not platform:
            return location
        
        url_lower = url.lower()
        config = cls.PLATFORM_PATTERNS.get(platform)
        
        if not config or 'location_pattern' not in config:
            return location
        
        # Extract location based on platform pattern
        pattern = config.get('location_pattern')
        if pattern:
            match = re.search(pattern, url_lower)
            if match:
                if platform == 'apartments.com':
                    # Format: city-state (e.g., chicago-il)
                    city_state = match.group(1)
                    parts = city_state.split('-')
                    if len(parts) >= 2:
                        # Last part might be state abbreviation
                        potential_state = parts[-1].upper()
                        if potential_state in cls.US_STATES:
                            location['state'] = potential_state
                            location['city'] = '-'.join(parts[:-1]).title()
                        else:
                            location['city'] = city_state.title()
                
                elif platform in ['redfin', 'trulia', 'zillow_fsbo', 'zillow_frbo', 'fsbo']:
                    # Format: /state/city or /state/city-name
                    if len(match.groups()) >= 2:
                        state = match.group(1).upper()
                        city = match.group(2).replace('-', ' ').title()
                        if state in cls.US_STATES:
                            location['state'] = state
                            location['city'] = city
                
                elif platform == 'hotpads':
                    # Format: /location or /zipcode
                    location_str = match.group(1)
                    # Try to detect if it's a zipcode (5 digits)
                    if re.match(r'^\d{5}$', location_str):
                        # It's a zipcode, we can't extract city/state from it easily
                        pass
                    else:
                        # Assume it's a city name
                        location['city'] = location_str.replace('-', ' ').title()
        
        return location
    
    @classmethod
    def detect_and_extract(cls, url: str) -> Tuple[Optional[str], Dict[str, Optional[str]]]:
        """
        Detect platform and extract location in one call.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Tuple of (platform, location_dict)
        """
        platform = cls.detect_platform(url)
        location = cls.extract_location(url, platform)
        return platform, location

