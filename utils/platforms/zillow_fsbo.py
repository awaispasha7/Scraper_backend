"""
Zillow FSBO platform search module.
Isolated from other platforms to prevent cascading failures.

Constructs URLs directly without browser automation.
URL pattern: https://www.zillow.com/{city}-{state}/fsbo/
Examples:
  - https://www.zillow.com/chicago-il/fsbo/
  - https://www.zillow.com/los-angeles-ca/fsbo/
  - https://www.zillow.com/washington-dc/fsbo/
  - https://www.zillow.com/minneapolis-mn/fsbo/
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _try_construct_zillow_fsbo_url(location: str) -> Optional[str]:
    """
    Construct a Zillow FSBO URL directly from location string.
    URL pattern: /{city}-{state}/fsbo/  (e.g., /chicago-il/fsbo/, /los-angeles-ca/fsbo/)
    
    Args:
        location: Location string (e.g., "Chicago, IL", "Los Angeles, CA", "Washington, DC")
    
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
            
            return f"https://www.zillow.com/{city_formatted}-{state_code}/fsbo/"
        
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
                
                return f"https://www.zillow.com/{city_formatted}-{state_code}/fsbo/"
        
        # Pattern 3: Just city name - try to construct with common state mappings
        city_formatted = location_clean.lower().replace(' ', '-').replace(',', '')
        city_formatted = re.sub(r'[^a-z0-9-]', '', city_formatted)
        city_formatted = re.sub(r'-+', '-', city_formatted)
        
        # Common city -> state mappings
        city_state_defaults = {
            'chicago': 'il', 'los-angeles': 'ca', 'washington': 'dc', 'minneapolis': 'mn',
            'new-york': 'ny', 'san-francisco': 'ca', 'san-diego': 'ca', 'houston': 'tx',
            'phoenix': 'az', 'philadelphia': 'pa', 'san-antonio': 'tx', 'dallas': 'tx',
            'san-jose': 'ca', 'austin': 'tx', 'jacksonville': 'fl', 'fort-worth': 'tx',
            'columbus': 'oh', 'charlotte': 'nc', 'indianapolis': 'in', 'seattle': 'wa',
            'denver': 'co', 'boston': 'ma', 'el-paso': 'tx', 'detroit': 'mi'
        }
        
        city_lower = city_formatted.strip()
        state_code = city_state_defaults.get(city_lower, 'ny')  # Default to NY
        
        return f"https://www.zillow.com/{city_formatted}-{state_code}/fsbo/"
        
    except Exception as e:
        logger.warning(f"[ZillowFSBO] Error constructing Zillow FSBO URL: {e}")
        return None


def search_zillow_fsbo(location: str) -> Optional[str]:
    """
    Search Zillow FSBO for a location by constructing the URL directly.
    No browser automation - just constructs and returns the URL.
    
    Args:
        location: Location string (e.g., "Chicago, IL", "Los Angeles, CA", "Washington, DC")
    
    Returns:
        Constructed URL string or None if construction fails
    
    Examples:
        >>> search_zillow_fsbo("Chicago, IL")
        'https://www.zillow.com/chicago-il/fsbo/'
        >>> search_zillow_fsbo("Los Angeles, CA")
        'https://www.zillow.com/los-angeles-ca/fsbo/'
        >>> search_zillow_fsbo("Washington, DC")
        'https://www.zillow.com/washington-dc/fsbo/'
    """
    location_clean = location.strip()
    logger.info(f"[ZillowFSBO] Constructing Zillow FSBO URL for: {location_clean}")
    
    # Construct URL directly (no browser needed)
    constructed_url = _try_construct_zillow_fsbo_url(location_clean)
    
    if not constructed_url:
        print(f"[ZillowFSBO] Warning: Could not construct URL from location: {location_clean}")
        logger.warning(f"[ZillowFSBO] URL construction failed for: {location_clean}")
        return None
    
    print(f"[ZillowFSBO] Constructed URL: {constructed_url}")
    logger.info(f"[ZillowFSBO] Constructed URL: {constructed_url}")
    
    return constructed_url
