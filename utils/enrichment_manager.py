import os
import sys
import json
import logging
from typing import Optional, Dict, List, Any
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Add parent dir to path to import utils
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.address_utils import normalize_address, generate_address_hash
from utils.placeholder_utils import clean_owner_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnrichmentManager:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def process_listing(self, listing_data: Dict[str, Any], listing_source: Optional[str] = None) -> str:
        """
        PAID-SAFE: Main entry point for scrapers after inserting a listing.
        
        CRITICAL SAFETY RULES:
        1. If enrichment_state exists with terminal status -> DO NOT MODIFY status
        2. Only create new queue entries for truly missing data
        3. Never queue if BatchData was already attempted
        """
        raw_address = listing_data.get('address')
        if not raw_address:
            logger.warning("Listing missing address, skipping enrichment check.")
            return None

        normalized = normalize_address(raw_address)
        address_hash = generate_address_hash(normalized)

        # STEP 1: Check existing enrichment state FIRST (paid safety check)
        existing = self._get_enrichment_state(address_hash)
        
        # TERMINAL STATES - Never modify status, never re-queue
        # These states mean BatchData was already attempted or scraped data was complete
        TERMINAL_STATES = ['enriched', 'no_owner_data', 'failed', 'checking']
        
        if existing and existing.get('status') in TERMINAL_STATES:
            logger.info(f"Address {address_hash[:8]} already in terminal state '{existing['status']}'. No action needed.")
            # Just update listing_source if missing in existing record
            if listing_source and not existing.get('listing_source'):
                self._update_listing_source(address_hash, listing_source)
            return address_hash

        # STEP 2: Process scraped owner data
        scraped_name = listing_data.get('owner_name')
        scraped_email = listing_data.get('owner_email') 
        scraped_phone = listing_data.get('owner_phone')
        
        # Handle lists if they were passed (some scrapers return lists)
        if isinstance(scraped_email, list): scraped_email = scraped_email[0] if scraped_email else None
        if isinstance(scraped_phone, list): scraped_phone = scraped_phone[0] if scraped_phone else None

        from utils.placeholder_utils import clean_owner_data, is_owner_data_complete
        
        clean_name, clean_email, clean_phone = clean_owner_data(scraped_name, scraped_email, scraped_phone)
        has_any_valid_data = any([clean_name, clean_email, clean_phone])

        # STEP 3: If we have valid scraped data, save it
        if has_any_valid_data:
            self._upsert_owner(address_hash, clean_name, clean_email, clean_phone, 
                              listing_data.get('mailing_address'), source='scraped', 
                              listing_source=listing_source)
            
            # Check if data is COMPLETE (all 3 fields valid AND mailing address)
            is_complete, _ = is_owner_data_complete(scraped_name, scraped_email, scraped_phone, listing_data.get('mailing_address'))
            
            if is_complete:
                # Complete data - mark as enriched, no BatchData needed
                self._set_enrichment_state(address_hash, normalized, 'enriched', 
                                           locked=True, source_used='scraped', 
                                           listing_source=listing_source)
            else:
                # Partial data (possibly missing mailing address) - only queue if no existing state
                if not existing:
                    self._set_enrichment_state(address_hash, normalized, 'never_checked',
                                              locked=False, source_used=None,
                                              listing_source=listing_source)
        else:
            # No valid scraped data - queue for BatchData if no existing state
            if not existing:
                self._set_enrichment_state(address_hash, normalized, 'never_checked',
                                          locked=False, source_used=None,
                                          listing_source=listing_source)

        return address_hash

    def _get_enrichment_state(self, address_hash: str):
        try:
            response = self.supabase.table("property_owner_enrichment_state").select("*").eq("address_hash", address_hash).maybe_single().execute()
            return response.data
        except Exception as e:
            logger.error(f"Error checking enrichment state: {e}")
            return None

    def _upsert_owner(self, address_hash: str, name: str, email: str, phone: str, mailing: str, source: str, listing_source: Optional[str] = None):
        try:
            data = {
                "address_hash": address_hash,
                "owner_name": name,
                "owner_email": email,
                "owner_phone": phone,
                "mailing_address": mailing,
                "source": source,
                "listing_source": listing_source
            }
            # Only update if fields were None before or if coming from BatchData (Phase 5)
            self.supabase.table("property_owners").upsert(data, on_conflict="address_hash").execute()
            logger.info(f"Upserted owner data for {address_hash[:8]}...")
        except Exception as e:
            logger.error(f"Error upserting owner: {e}")

    def _update_listing_source(self, address_hash: str, listing_source: str):
        try:
            self.supabase.table("property_owner_enrichment_state").update({"listing_source": listing_source}).eq("address_hash", address_hash).execute()
        except Exception as e:
            logger.error(f"Error updating listing source: {e}")

    def _set_enrichment_state(self, address_hash: str, normalized: str, status: str, locked: bool, source_used: str, listing_source: Optional[str] = None):
        try:
            # Re-check existence to prevent race conditions implicitly (upsert handles it, but logic matters)
            # This method acts as an upsert for new records usually.
            data = {
                "address_hash": address_hash,
                "normalized_address": normalized,
                "status": status,
                "locked": locked,
                "source_used": source_used,
                "listing_source": listing_source,
                "missing_fields": {
                    "owner_name": True,
                    "owner_email": True,
                    "owner_phone": True
                }
            }
            # Do NOT overwrite existing terminal states if we somehow got here
            # But caller ensures we don't.
            self.supabase.table("property_owner_enrichment_state").upsert(data, on_conflict="address_hash").execute()
            logger.info(f"Set enrichment state to {status} for {address_hash[:8]}...")
        except Exception as e:
            logger.error(f"Error setting enrichment state: {e}")
