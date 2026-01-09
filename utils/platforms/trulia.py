"""
Trulia platform search module.
Isolated from other platforms to prevent cascading failures.

Uses direct URL construction only - no browser automation.
Trulia URL pattern: /{STATE}/{City}/  (e.g., /MN/Minneapolis/, /NY/New_York/)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def construct_trulia_url(location: str) -> Optional[str]:
    """
    Construct a Trulia URL directly from location string.
    Trulia URL patterns: /{STATE}/{City}/  (e.g., /MN/Minneapolis/, /NY/New_York/)
    
    This is a foolproof implementation with comprehensive city-to-state mappings.
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY", "Minneapolis")
        
    Returns:
        Constructed Trulia URL or None if location cannot be parsed
    """
    try:
        location_clean = location.strip()
        logger.info(f"[Trulia] Constructing Trulia URL for: {location_clean}")
        
        # State abbreviations mapping (full name -> abbrev)
        state_mapping = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
            'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
            'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
            'washington dc': 'DC', 'dc': 'DC'
        }
        
        # Comprehensive city-to-state mapping for major cities (when only city name is provided)
        city_to_state = {
            'minneapolis': 'MN', 'new york': 'NY', 'los angeles': 'CA', 'chicago': 'IL',
            'houston': 'TX', 'phoenix': 'AZ', 'philadelphia': 'PA', 'san antonio': 'TX',
            'san diego': 'CA', 'dallas': 'TX', 'san jose': 'CA', 'austin': 'TX',
            'jacksonville': 'FL', 'fort worth': 'TX', 'columbus': 'OH', 'charlotte': 'NC',
            'san francisco': 'CA', 'indianapolis': 'IN', 'seattle': 'WA', 'denver': 'CO',
            'washington': 'DC', 'boston': 'MA', 'el paso': 'TX', 'detroit': 'MI',
            'nashville': 'TN', 'portland': 'OR', 'oklahoma city': 'OK', 'las vegas': 'NV',
            'memphis': 'TN', 'louisville': 'KY', 'baltimore': 'MD', 'milwaukee': 'WI',
            'albuquerque': 'NM', 'tucson': 'AZ', 'fresno': 'CA', 'sacramento': 'CA',
            'kansas city': 'MO', 'mesa': 'AZ', 'atlanta': 'GA', 'omaha': 'NE',
            'colorado springs': 'CO', 'raleigh': 'NC', 'virginia beach': 'VA', 'miami': 'FL',
            'oakland': 'CA', 'tulsa': 'OK', 'cleveland': 'OH', 'wichita': 'KS',
            'arlington': 'TX', 'new orleans': 'LA', 'tampa': 'FL', 'honolulu': 'HI',
            'st. louis': 'MO', 'st louis': 'MO', 'cincinnati': 'OH', 'pittsburgh': 'PA',
            'buffalo': 'NY', 'st. paul': 'MN', 'st paul': 'MN', 'corpus christi': 'TX',
            'aurora': 'CO', 'newark': 'NJ', 'plano': 'TX', 'henderson': 'NV',
            'lincoln': 'NE', 'greensboro': 'NC', 'durham': 'NC', 'jersey city': 'NJ',
            'chula vista': 'CA', 'scottsdale': 'AZ', 'norfolk': 'VA', 'madison': 'WI',
            'orlando': 'FL', 'chandler': 'AZ', 'laredo': 'TX', 'lubbock': 'TX',
            'garland': 'TX', 'hialeah': 'FL', 'reno': 'NV', 'chesapeake': 'VA',
            'gilbert': 'AZ', 'baton rouge': 'LA', 'irving': 'TX', 'glendale': 'AZ',
            'richmond': 'VA', 'boise': 'ID', 'san bernardino': 'CA', 'spokane': 'WA',
            'birmingham': 'AL', 'modesto': 'CA', 'rochester': 'NY', 'des moines': 'IA',
            'fayetteville': 'NC', 'tacoma': 'WA', 'fontana': 'CA', 'oxnard': 'CA',
            'moreno valley': 'CA', 'shreveport': 'LA', 'aurora': 'IL', 'yonkers': 'NY',
            'akron': 'OH', 'huntington beach': 'CA', 'little rock': 'AR', 'amarillo': 'TX',
            'grand rapids': 'MI', 'mobile': 'AL', 'salt lake city': 'UT', 'tallahassee': 'FL',
            'grand prairie': 'TX', 'overland park': 'KS', 'knoxville': 'TN',
            'winston-salem': 'NC', 'winston salem': 'NC', 'sioux falls': 'SD',
            'peoria': 'AZ', 'providence': 'RI', 'gainesville': 'FL', 'frisco': 'TX',
            'tempe': 'AZ', 'mcallen': 'TX', 'fort lauderdale': 'FL', 'brownsville': 'TX',
            'ontario': 'CA', 'santa ana': 'CA', 'elgin': 'IL', 'vancouver': 'WA',
            'nampa': 'ID', 'mckinney': 'TX', 'fremont': 'CA', 'stockton': 'CA',
            'richmond': 'CA', 'irvine': 'CA', 'troy': 'NY', 'alabama': 'NY',
            # Additional common cities
            'ann arbor': 'MI', 'arlington': 'VA', 'atlanta': 'GA', 'austin': 'TX',
            'bakersfield': 'CA', 'baton rouge': 'LA', 'birmingham': 'AL', 'boise': 'ID',
            'bridgeport': 'CT', 'brownsville': 'TX', 'cape coral': 'FL', 'cary': 'NC',
            'cedar rapids': 'IA', 'charleston': 'SC', 'chesapeake': 'VA', 'chula vista': 'CA',
            'cincinnati': 'OH', 'colorado springs': 'CO', 'columbia': 'SC', 'columbus': 'GA',
            'corpus christi': 'TX', 'durham': 'NC', 'el paso': 'TX', 'fort wayne': 'IN',
            'fort worth': 'TX', 'fremont': 'CA', 'fresno': 'CA', 'garland': 'TX',
            'gilbert': 'AZ', 'glendale': 'AZ', 'greensboro': 'NC', 'henderson': 'NV',
            'hialeah': 'FL', 'honolulu': 'HI', 'houston': 'TX', 'huntington beach': 'CA',
            'indianapolis': 'IN', 'irvine': 'CA', 'jackson': 'MS', 'jacksonville': 'FL',
            'jersey city': 'NJ', 'kansas city': 'MO', 'laredo': 'TX', 'las vegas': 'NV',
            'lexington': 'KY', 'lincoln': 'NE', 'little rock': 'AR', 'long beach': 'CA',
            'los angeles': 'CA', 'louisville': 'KY', 'lubbock': 'TX', 'madison': 'WI',
            'memphis': 'TN', 'mesa': 'AZ', 'miami': 'FL', 'milwaukee': 'WI',
            'minneapolis': 'MN', 'mobile': 'AL', 'modesto': 'CA', 'montgomery': 'AL',
            'moreno valley': 'CA', 'naples': 'FL', 'nashville': 'TN', 'new orleans': 'LA',
            'newark': 'NJ', 'norfolk': 'VA', 'north las vegas': 'NV', 'oakland': 'CA',
            'oklahoma city': 'OK', 'omaha': 'NE', 'orlando': 'FL', 'oxnard': 'CA',
            'philadelphia': 'PA', 'phoenix': 'AZ', 'pittsburgh': 'PA', 'plano': 'TX',
            'portland': 'OR', 'raleigh': 'NC', 'reno': 'NV', 'richmond': 'VA',
            'riverside': 'CA', 'rochester': 'NY', 'sacramento': 'CA', 'saint paul': 'MN',
            'salem': 'OR', 'salt lake city': 'UT', 'san antonio': 'TX', 'san bernardino': 'CA',
            'san diego': 'CA', 'san francisco': 'CA', 'san jose': 'CA', 'santa ana': 'CA',
            'scottsdale': 'AZ', 'seattle': 'WA', 'shreveport': 'LA', 'sioux falls': 'SD',
            'spokane': 'WA', 'st. louis': 'MO', 'st. paul': 'MN', 'st louis': 'MO',
            'st paul': 'MN', 'stockton': 'CA', 'tacoma': 'WA', 'tallahassee': 'FL',
            'tampa': 'FL', 'tempe': 'AZ', 'toledo': 'OH', 'tucson': 'AZ',
            'tulsa': 'OK', 'virginia beach': 'VA', 'washington': 'DC', 'wichita': 'KS',
            'winston-salem': 'NC', 'winston salem': 'NC', 'worcester': 'MA'
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
                state_abbrev = state_part.upper()
            else:
                # Try to find state abbreviation from full name
                state_lower = state_part.lower()
                if state_lower in state_mapping:
                    state_abbrev = state_mapping[state_lower]
        
        # Pattern 2: "City State" (space separated, 2-letter state at end)
        if not city or not state_abbrev:
            match = re.match(r'^(.+?)\s+([A-Z]{2})$', location_clean)
            if match:
                city = match.group(1).strip()
                state_abbrev = match.group(2).strip().upper()
        
        # Pattern 3: Try to find state abbreviation anywhere in the string
        if not state_abbrev:
            # Look for 2-letter state codes
            state_match = re.search(r'\b([A-Z]{2})\b', location_clean)
            if state_match:
                potential_state = state_match.group(1).upper()
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
        
        # Pattern 4: Try to find full state name
        if not state_abbrev:
            for state_name, abbrev in state_mapping.items():
                if state_name in location_clean.lower():
                    state_abbrev = abbrev
                    # Extract city (everything before the state name)
                    state_index = location_clean.lower().find(state_name)
                    city = location_clean[:state_index].strip()
                    break
        
        # If no city found, use the whole location as city (minus state)
        if not city:
            city = location_clean
            for state_name, abbrev in state_mapping.items():
                city = re.sub(rf'\b{state_name}\b', '', city, flags=re.IGNORECASE).strip()
            city = re.sub(rf'\b{state_abbrev}\b', '', city, flags=re.IGNORECASE).strip() if state_abbrev else city
            city = re.sub(r'[,\s]+', ' ', city).strip()
        
        if not city:
            logger.warning(f"[Trulia] Could not extract city from location: {location_clean}")
            print(f"[Trulia] ⚠️ Could not extract city from location")
            return None
        
        if not state_abbrev:
            logger.warning(f"[Trulia] Could not extract state from location: {location_clean}")
            print(f"[Trulia] ⚠️ Could not extract state from location")
            return None
        
        # Convert city to Trulia URL format: replace spaces with underscores, preserve capitalization
        # Trulia uses underscores and preserves case (e.g., New_York, Los_Angeles)
        city_slug = city.strip()
        # Replace spaces with underscores
        city_slug = re.sub(r'\s+', '_', city_slug)
        # Remove special characters except underscores and hyphens
        city_slug = re.sub(r'[^\w\s_-]', '', city_slug)
        # Replace multiple underscores with single
        city_slug = re.sub(r'_+', '_', city_slug)
        # Remove leading/trailing underscores
        city_slug = city_slug.strip('_')
        
        # Construct URL
        url = f"https://www.trulia.com/{state_abbrev}/{city_slug}/"
        logger.info(f"[Trulia] ✓ Constructed Trulia URL: {url}")
        print(f"[Trulia] ✓ Constructed Trulia URL directly: {url}")
        return url
        
    except Exception as e:
        logger.error(f"[Trulia] Error constructing Trulia URL: {e}")
        print(f"[Trulia] Error constructing Trulia URL: {e}")
        return None


def search_trulia(location: str) -> Optional[str]:
    """
    Search Trulia for a location using direct URL construction only.
    
    No browser automation - constructs URL directly from location string.
    This is much faster and more reliable than automation.
    
    Args:
        location: Location string (e.g., "Los Angeles, CA", "New York NY", "Minneapolis")
        
    Returns:
        Constructed Trulia URL or None if location cannot be parsed
    """
    location_clean = location.strip()
    logger.info(f"[Trulia] Searching Trulia for: {location_clean}")
    
    # Use URL construction only (no browser automation)
    print(f"[Trulia] Constructing URL directly (no browser needed)...")
    result = construct_trulia_url(location_clean)
    if result:
        print(f"[Trulia] ✓ URL construction succeeded!")
        return result
    else:
        print(f"[Trulia] ✗ URL construction failed")
        logger.warning(f"[Trulia] Could not construct Trulia URL for: {location_clean}")
        return None
