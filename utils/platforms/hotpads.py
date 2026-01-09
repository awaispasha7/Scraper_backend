"""
Hotpads platform search module.
Isolated from other platforms to prevent cascading failures.
"""

import re
import logging
from typing import Optional

from .base import get_driver

logger = logging.getLogger(__name__)


def construct_hotpads_url(location: str, property_type: str = "apartments") -> Optional[str]:
    """
    Construct Hotpads URL directly from location name without browser automation.
    
    Pattern: https://hotpads.com/{city-name}-{state-abbrev}/{property-type}-for-rent
    Examples:
        - "Los Angeles, CA" -> "https://hotpads.com/los-angeles-ca/apartments-for-rent"
        - "Los Angeles, CA", "houses" -> "https://hotpads.com/los-angeles-ca/houses-for-rent"
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY", "Chicago")
        property_type: Property type (default: "apartments"). Options: "apartments", "houses", "condos", "townhomes", etc.
        
    Returns:
        Constructed Hotpads URL or None if location cannot be parsed
    """
    location_clean = location.strip()
    logger.info(f"[Hotpads] Constructing Hotpads URL for: {location_clean}")
    
    # State abbreviations mapping (full name -> abbrev)
    state_mapping = {
        'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
        'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
        'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi', 'idaho': 'id',
        'illinois': 'il', 'indiana': 'in', 'iowa': 'ia', 'kansas': 'ks',
        'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
        'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn', 'mississippi': 'ms',
        'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne', 'nevada': 'nv',
        'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm', 'new york': 'ny',
        'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh', 'oklahoma': 'ok',
        'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri', 'south carolina': 'sc',
        'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx', 'utah': 'ut',
        'vermont': 'vt', 'virginia': 'va', 'washington': 'wa', 'west virginia': 'wv',
        'wisconsin': 'wi', 'wyoming': 'wy', 'district of columbia': 'dc'
    }
    
    # City-to-state mapping for major cities (when only city name is provided)
    city_to_state = {
        'minneapolis': 'mn', 'new york': 'ny', 'los angeles': 'ca', 'chicago': 'il',
        'houston': 'tx', 'phoenix': 'az', 'philadelphia': 'pa', 'san antonio': 'tx',
        'san diego': 'ca', 'dallas': 'tx', 'san jose': 'ca', 'austin': 'tx',
        'jacksonville': 'fl', 'fort worth': 'tx', 'columbus': 'oh', 'charlotte': 'nc',
        'san francisco': 'ca', 'indianapolis': 'in', 'seattle': 'wa', 'denver': 'co',
        'washington': 'dc', 'boston': 'ma', 'el paso': 'tx', 'detroit': 'mi',
        'nashville': 'tn', 'portland': 'or', 'oklahoma city': 'ok', 'las vegas': 'nv',
        'memphis': 'tn', 'louisville': 'ky', 'baltimore': 'md', 'milwaukee': 'wi',
        'albuquerque': 'nm', 'tucson': 'az', 'fresno': 'ca', 'sacramento': 'ca',
        'kansas city': 'mo', 'mesa': 'az', 'atlanta': 'ga', 'omaha': 'ne',
        'colorado springs': 'co', 'raleigh': 'nc', 'virginia beach': 'va', 'miami': 'fl',
        'oakland': 'ca', 'tulsa': 'ok', 'cleveland': 'oh', 'wichita': 'ks',
        'arlington': 'tx', 'new orleans': 'la', 'tampa': 'fl', 'honolulu': 'hi',
        'st. louis': 'mo', 'st louis': 'mo', 'cincinnati': 'oh', 'pittsburgh': 'pa',
        'buffalo': 'ny', 'st. paul': 'mn', 'st paul': 'mn', 'corpus christi': 'tx',
        'aurora': 'co', 'newark': 'nj', 'plano': 'tx', 'henderson': 'nv',
        'lincoln': 'ne', 'greensboro': 'nc', 'durham': 'nc', 'jersey city': 'nj',
        'chula vista': 'ca', 'scottsdale': 'az', 'norfolk': 'va', 'madison': 'wi',
        'orlando': 'fl', 'chandler': 'az', 'laredo': 'tx', 'lubbock': 'tx',
        'garland': 'tx', 'hialeah': 'fl', 'reno': 'nv', 'chesapeake': 'va',
        'gilbert': 'az', 'baton rouge': 'la', 'irving': 'tx', 'glendale': 'az',
        'richmond': 'va', 'boise': 'id', 'san bernardino': 'ca', 'spokane': 'wa',
        'birmingham': 'al', 'modesto': 'ca', 'rochester': 'ny', 'des moines': 'ia',
        'fayetteville': 'nc', 'tacoma': 'wa', 'fontana': 'ca', 'oxnard': 'ca',
        'moreno valley': 'ca', 'shreveport': 'la', 'aurora': 'il', 'yonkers': 'ny',
        'akron': 'oh', 'huntington beach': 'ca', 'little rock': 'ar', 'amarillo': 'tx',
        'grand rapids': 'mi', 'mobile': 'al', 'salt lake city': 'ut', 'tallahassee': 'fl',
        'grand prairie': 'tx', 'overland park': 'ks', 'knoxville': 'tn',
        'winston-salem': 'nc', 'winston salem': 'nc', 'sioux falls': 'sd',
        'peoria': 'az', 'providence': 'ri', 'gainesville': 'fl', 'frisco': 'tx',
        'tempe': 'az', 'mcallen': 'tx', 'fort lauderdale': 'fl', 'brownsville': 'tx',
        'ontario': 'ca', 'santa ana': 'ca', 'elgin': 'il', 'vancouver': 'wa',
        'nampa': 'id', 'mckinney': 'tx', 'fremont': 'ca', 'stockton': 'ca',
        'richmond': 'ca', 'irvine': 'ca', 'san bernardino': 'ca', 'spokane': 'wa'
    }
    
    # Try to extract city and state from location string
    city = None
    state_abbrev = None
    
    # Pattern 1: "City, State" or "City, ST" (comma separated)
    match = re.match(r'^(.+?),\s*([A-Z]{2}|[A-Za-z\s]+)$', location_clean)
    if match:
        city = match.group(1).strip()
        state_part = match.group(2).strip()
        
        # Check if state_part is already an abbreviation (2 letters)
        if len(state_part) == 2 and state_part.upper() in [s.upper() for s in state_mapping.values()]:
            state_abbrev = state_part.lower()
        else:
            # Try to find state abbreviation from full name
            state_lower = state_part.lower()
            if state_lower in state_mapping:
                state_abbrev = state_mapping[state_lower]
    
    # Pattern 2: "City ST" (space separated, 2-letter state at end)
    if not city or not state_abbrev:
        match = re.match(r'^(.+?)\s+([A-Z]{2})$', location_clean)
        if match:
            city = match.group(1).strip()
            state_abbrev = match.group(2).strip().lower()
    
    # Pattern 3: Try to find state abbreviation anywhere in the string
    if not state_abbrev:
        # Look for 2-letter state codes
        state_match = re.search(r'\b([A-Z]{2})\b', location_clean)
        if state_match:
            potential_state = state_match.group(1).lower()
            if potential_state in state_mapping.values():
                state_abbrev = potential_state
                # Extract city (everything before the state)
                city = location_clean[:state_match.start()].strip()
    
    # Before checking for full state names, check city-to-state mapping first
    # This handles cases like "New York" which is both a city and a state name
    if not state_abbrev:
        location_lower = location_clean.lower().strip()
        # Try exact match first
        if location_lower in city_to_state:
            state_abbrev = city_to_state[location_lower]
            city = location_clean  # Use the full location as city
        else:
            # Try to find a city name that matches (handles multi-word cities)
            for city_name, state_code in city_to_state.items():
                if location_lower == city_name or location_lower.startswith(city_name + ' ') or location_lower.endswith(' ' + city_name):
                    state_abbrev = state_code
                    city = location_clean  # Use the full location as city
                    break
    
    # If we still don't have a state, try to find full state name
    if not state_abbrev:
        for state_name, abbrev in state_mapping.items():
            if state_name in location_clean.lower():
                state_abbrev = abbrev
                # Extract city (everything before the state name)
                state_index = location_clean.lower().find(state_name)
                city = location_clean[:state_index].strip()
                break
    
    # If no state found, we can't construct a valid URL
    if not state_abbrev:
        logger.warning(f"[Hotpads] Could not extract state from location: {location_clean}")
        print(f"[Hotpads] ⚠️ Could not extract state from location, falling back to browser automation")
        return None
    
    # If no city found, use the whole location as city (minus state)
    if not city:
        # Remove state from location
        city = location_clean
        for state_name, abbrev in state_mapping.items():
            city = re.sub(rf'\b{state_name}\b', '', city, flags=re.IGNORECASE).strip()
        city = re.sub(rf'\b{state_abbrev}\b', '', city, flags=re.IGNORECASE).strip()
        city = re.sub(r'[,\s]+', ' ', city).strip()
    
    if not city:
        logger.warning(f"[Hotpads] Could not extract city from location: {location_clean}")
        print(f"[Hotpads] ⚠️ Could not extract city from location, falling back to browser automation")
        return None
    
    # Convert city to URL format: lowercase, replace spaces/special chars with hyphens
    city_slug = city.lower()
    # Replace spaces and special characters with hyphens
    city_slug = re.sub(r'[^\w\s-]', '', city_slug)  # Remove special chars
    city_slug = re.sub(r'\s+', '-', city_slug)  # Replace spaces with hyphens
    city_slug = re.sub(r'-+', '-', city_slug)  # Replace multiple hyphens with single
    city_slug = city_slug.strip('-')  # Remove leading/trailing hyphens
    
    # Normalize property type (lowercase, handle plural/singular)
    property_type_clean = property_type.lower().strip()
    # Ensure it ends with 's' for plural (apartments, houses, condos, townhomes)
    if not property_type_clean.endswith('s') and property_type_clean not in ['condos', 'townhomes']:
        # Add 's' if it's a singular form
        if property_type_clean in ['apartment', 'house', 'condo', 'townhome']:
            property_type_clean = property_type_clean + 's'
    
    # Construct URL with property type
    url = f"https://hotpads.com/{city_slug}-{state_abbrev}/{property_type_clean}-for-rent"
    logger.info(f"[Hotpads] ✓ Constructed Hotpads URL: {url}")
    print(f"[Hotpads] ✓ Constructed Hotpads URL directly: {url}")
    return url


def search_hotpads(location: str, property_type: str = "apartments") -> Optional[str]:
    """Search Hotpads for a location using direct URL construction.
    
    Constructs the Hotpads URL directly from location and property type.
    No browser automation needed - much faster and more reliable!
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY")
        property_type: Property type (default: "apartments"). Options: "apartments", "houses", "condos", "townhomes"
        
    Returns:
        Constructed Hotpads URL or None if location cannot be parsed
    """
    location_clean = location.strip()
    logger.info(f"[Hotpads] Searching Hotpads for: {location_clean} (property_type: {property_type})")
    
    # Construct URL directly (no browser needed!)
    url = construct_hotpads_url(location_clean, property_type)
    if url:
        print(f"[Hotpads] ✓ Using direct URL construction (no browser needed)")
        return url
    
    # If URL construction failed, return None
    logger.warning(f"[Hotpads] Could not construct Hotpads URL for: {location_clean}")
    print(f"[Hotpads] ⚠️ Could not construct URL - location format may be invalid")
    return None

