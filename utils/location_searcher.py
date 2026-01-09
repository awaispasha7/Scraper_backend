"""
Location Search Utilities
Searches platforms to get the actual listing URL from a location name.
Constructs URLs directly using platform-specific URL patterns.

This module has been refactored to use modular platform-specific modules.
Each platform is isolated to prevent cascading failures.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class LocationSearcher:
    """Search platforms for location and return the actual listing URL by constructing URLs directly"""
    
    @classmethod
    def search_platform(cls, platform: str, location: str, property_type: str = "apartments") -> Optional[str]:
        """
        Search a platform for a location and return the actual listing URL.
        
        Args:
            platform: Platform name (e.g., "hotpads", "trulia", "apartments", "redfin", "zillow_fsbo", "zillow_frbo", "fsbo")
            location: Location string (e.g., "Los Angeles, CA", "New York NY")
            property_type: Property type (default: "apartments"). Only used for Hotpads.
        
        Returns:
            URL string or None if search failed
        """
        platform_lower = platform.strip().lower()
        
        try:
            if platform_lower == "hotpads":
                from .platforms.hotpads import search_hotpads
                return search_hotpads(location, property_type)
            elif platform_lower == "trulia":
                from .platforms.trulia import search_trulia
                return search_trulia(location)
            elif platform_lower == "apartments" or platform_lower == "apartments.com":
                from .platforms.apartments import search_apartments
                return search_apartments(location)
            elif platform_lower == "redfin":
                from .platforms.redfin import search_redfin
                return search_redfin(location)
            elif platform_lower == "zillow_fsbo":
                from .platforms.zillow_fsbo import search_zillow_fsbo
                return search_zillow_fsbo(location)
            elif platform_lower == "zillow_frbo":
                from .platforms.zillow_frbo import search_zillow_frbo
                return search_zillow_frbo(location)
            elif platform_lower == "fsbo":
                from .platforms.fsbo import search_fsbo
                return search_fsbo(location)
            else:
                logger.warning(f"[LocationSearcher] Unknown platform: {platform}")
            return None
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import platform module for {platform}: {e}")
            print(f"[LocationSearcher] ⚠️ Platform module for '{platform}' is corrupted or missing. Other platforms are unaffected.")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error searching {platform}: {e}")
            print(f"[LocationSearcher] ⚠️ Error in {platform} module: {e}. Other platforms are unaffected.")
        return None
    
    @classmethod
    def search_trulia(cls, location: str) -> Optional[str]:
        """Search Trulia for a location."""
        try:
            from .platforms.trulia import search_trulia as _search_trulia
            return _search_trulia(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Trulia module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Trulia search: {e}")
            return None
    
    @classmethod
    def search_apartments(cls, location: str) -> Optional[str]:
        """Search Apartments.com for a location."""
        try:
            from .platforms.apartments import search_apartments as _search_apartments
            return _search_apartments(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Apartments module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Apartments search: {e}")
            return None
    
    @classmethod
    def search_redfin(cls, location: str) -> Optional[str]:
        """Search Redfin for a location."""
        try:
            from .platforms.redfin import search_redfin as _search_redfin
            return _search_redfin(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Redfin module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Redfin search: {e}")
        return None
    
    @classmethod
    def search_zillow_fsbo(cls, location: str) -> Optional[str]:
        """Search Zillow FSBO for a location."""
        try:
            from .platforms.zillow_fsbo import search_zillow_fsbo as _search_zillow_fsbo
            return _search_zillow_fsbo(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Zillow FSBO module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Zillow FSBO search: {e}")
            return None
    
    @classmethod
    def search_zillow_frbo(cls, location: str) -> Optional[str]:
        """Search Zillow FRBO for a location."""
        try:
            from .platforms.zillow_frbo import search_zillow_frbo as _search_zillow_frbo
            return _search_zillow_frbo(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Zillow FRBO module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Zillow FRBO search: {e}")
            return None
    
    @classmethod
    def search_hotpads(cls, location: str, property_type: str = "apartments") -> Optional[str]:
        """Search Hotpads for a location."""
        try:
            from .platforms.hotpads import search_hotpads as _search_hotpads
            return _search_hotpads(location, property_type)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import Hotpads module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in Hotpads search: {e}")
            return None
    
    @classmethod
    def search_fsbo(cls, location: str) -> Optional[str]:
        """Search FSBO for a location."""
        try:
            from .platforms.fsbo import search_fsbo as _search_fsbo
            return _search_fsbo(location)
        except ImportError as e:
            logger.error(f"[LocationSearcher] Failed to import FSBO module: {e}")
            return None
        except Exception as e:
            logger.error(f"[LocationSearcher] Error in FSBO search: {e}")
            return None
