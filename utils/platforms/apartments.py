"""
Apartments.com platform search module.
Isolated from other platforms to prevent cascading failures.

Constructs URLs directly without browser automation.
URL pattern: https://www.apartments.com/{city}-{state_code}/
Examples:
  - https://www.apartments.com/minneapolis-mn/
  - https://www.apartments.com/los-angeles-ca/
  - https://www.apartments.com/washington-dc/
  - https://www.apartments.com/new-york-ny/
  - https://www.apartments.com/san-francisco-ca/
  - https://www.apartments.com/chicago-il/
  - https://www.apartments.com/anchorage-ak/
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _try_construct_apartments_url(location: str) -> Optional[str]:
    """
    Construct an Apartments.com URL directly from location string.
    URL pattern: /{city}-{state_code}/  (e.g., /minneapolis-mn/, /new-york-ny/)
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "Minneapolis MN", "Chicago, IL")
    
    Returns:
        Constructed URL string or None if construction fails
    """
    try:
        location_clean = location.strip()
        
        # Common state name to abbreviation mapping
        state_map = {
            'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar', 'california': 'ca',
            'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de', 'florida': 'fl', 'georgia': 'ga',
            'hawaii': 'hi', 'idaho': 'id', 'illinois': 'il', 'indiana': 'in', 'iowa': 'ia',
            'kansas': 'ks', 'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
            'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn', 'mississippi': 'ms', 'missouri': 'mo',
            'montana': 'mt', 'nebraska': 'ne', 'nevada': 'nv', 'new hampshire': 'nh', 'new jersey': 'nj',
            'new mexico': 'nm', 'new york': 'ny', 'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh',
            'oklahoma': 'ok', 'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri', 'south carolina': 'sc',
            'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx', 'utah': 'ut', 'vermont': 'vt',
            'virginia': 'va', 'washington': 'wa', 'west virginia': 'wv', 'wisconsin': 'wi', 'wyoming': 'wy',
            'district of columbia': 'dc', 'washington dc': 'dc', 'dc': 'dc'
        }
        
        # Try to parse "City, State" or "City, ST" format
        # Pattern 1: "City, State" or "City, ST"
        match = re.match(r'^(.+?)\s*,\s*([a-z]{2}|.+)$', location_clean, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
            state_input = match.group(2).strip().lower()
            
            # Convert state name to abbreviation if needed
            if len(state_input) == 2:
                state_code = state_input.lower()
            else:
                state_code = state_map.get(state_input, state_input.lower()[:2])  # Try state map, fallback to first 2 chars
            
            # Format city name (lowercase, replace spaces with hyphens)
            city_formatted = city.lower().replace(' ', '-').replace(',', '')
            city_formatted = re.sub(r'[^a-z0-9-]', '', city_formatted)  # Remove special chars
            city_formatted = re.sub(r'-+', '-', city_formatted)  # Replace multiple hyphens with single
            
            return f"https://www.apartments.com/{city_formatted}-{state_code}/"
        
        # Pattern 2: "City State" (no comma)
        # Try to split by space and check if last part is a state
        parts = location_clean.split()
        if len(parts) >= 2:
            # Check if last part is a state code
            last_part = parts[-1].lower()
            if last_part in state_map.values() or last_part in state_map:
                city = ' '.join(parts[:-1])
                state_input = last_part
                state_code = state_map.get(state_input, state_input) if state_input not in state_map.values() else state_input
                
                city_formatted = city.lower().replace(' ', '-').replace(',', '')
                city_formatted = re.sub(r'[^a-z0-9-]', '', city_formatted)
                city_formatted = re.sub(r'-+', '-', city_formatted)
                
                return f"https://www.apartments.com/{city_formatted}-{state_code}/"
        
        # Pattern 3: Just city name - try to construct with common state mappings
        city_formatted = location_clean.lower().replace(' ', '-').replace(',', '')
        city_formatted = re.sub(r'[^a-z0-9-]', '', city_formatted)
        city_formatted = re.sub(r'-+', '-', city_formatted)
        
        # Common city -> state mappings
        city_state_defaults = {
            'minneapolis': 'mn', 'new-york': 'ny', 'los-angeles': 'ca', 'chicago': 'il',
            'houston': 'tx', 'phoenix': 'az', 'philadelphia': 'pa', 'san-antonio': 'tx',
            'san-diego': 'ca', 'dallas': 'tx', 'san-jose': 'ca', 'austin': 'tx',
            'jacksonville': 'fl', 'fort-worth': 'tx', 'columbus': 'oh', 'charlotte': 'nc',
            'san-francisco': 'ca', 'indianapolis': 'in', 'seattle': 'wa', 'denver': 'co',
            'washington': 'dc', 'boston': 'ma', 'el-paso': 'tx', 'detroit': 'mi',
            'anchorage': 'ak', 'new-york': 'ny', 'alabama': 'al'
        }
        
        city_lower = city_formatted.strip()
        state_code = city_state_defaults.get(city_lower, 'ny')  # Default to NY
        
        return f"https://www.apartments.com/{city_formatted}-{state_code}/"
        
    except Exception as e:
        logger.warning(f"[Apartments] Error constructing Apartments.com URL: {e}")
        return None


def search_apartments(location: str) -> Optional[str]:
    """
    Search Apartments.com for a location by constructing the URL directly.
    No browser automation - just constructs and returns the URL.
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "Minneapolis MN", "Chicago, IL")
    
    Returns:
        Constructed URL string or None if construction fails
    
    Examples:
        >>> search_apartments("Minneapolis, MN")
        'https://www.apartments.com/minneapolis-mn/'
        >>> search_apartments("Los Angeles, CA")
        'https://www.apartments.com/los-angeles-ca/'
        >>> search_apartments("Washington, DC")
        'https://www.apartments.com/washington-dc/'
    """
    location_clean = location.strip()
    logger.info(f"[Apartments] Constructing Apartments.com URL for: {location_clean}")
    
    # Construct URL directly (no browser needed)
    constructed_url = _try_construct_apartments_url(location_clean)
    
    if not constructed_url:
        print(f"[Apartments] Warning: Could not construct URL from location: {location_clean}")
        logger.warning(f"[Apartments] URL construction failed for: {location_clean}")
        return None
    
    print(f"[Apartments] Constructed URL: {constructed_url}")
    logger.info(f"[Apartments] Constructed URL: {constructed_url}")
    
    return constructed_url
