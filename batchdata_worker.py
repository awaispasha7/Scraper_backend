import os
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Add shared utils
import sys
project_root = Path(__file__).resolve().parents[0]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from utils.address_utils import normalize_address
from utils.placeholder_utils import clean_owner_data

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load env vars
load_dotenv()

class BatchDataWorker:
    def __init__(self):
        # Supabase config
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials missing.")
        self.supabase: Client = create_client(url, key)
        
        # BatchData config
        self.api_key = os.getenv("BATCHDATA_API_KEY")
        self.api_enabled = os.getenv("BATCHDATA_ENABLED", "false").lower() == "true"
        self.daily_limit = int(os.getenv("BATCHDATA_DAILY_LIMIT", "50"))
        # Phase 2: Add DRY RUN flag
        self.dry_run = os.getenv("BATCHDATA_DRY_RUN", "false").lower() == "true"
        self.cost_per_call = 0.085  # USD (Updated from $0.07)
        self.api_url = "https://api.batchdata.com/api/v1/property/skip-trace"
        
    def check_daily_usage(self) -> int:
        """Counts how many BatchData calls were made in the last 24 hours."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        try:
            response = self.supabase.table("property_owner_enrichment_state") \
                .select("id", count="exact") \
                .eq("source_used", "batchdata") \
                .gte("checked_at", today_start) \
                .execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Error checking daily usage: {e}")
            return 9999 # Safety: assume limit reached on error

    def parse_address_string(self, address: str) -> Dict[str, str]:
        """
        Robustly split address into components. 
        Handles "Street, City, State Zip" OR "STREET CITY STATE ZIP"
        """
        if not address:
            return {"street": "", "city": "", "state": "", "zip": ""}
        
        result = {"street": "", "city": "", "state": "", "zip": ""}
        
        # 1. Try splitting by comma first (Best for original addresses)
        if ',' in address:
            parts = [p.strip() for p in address.split(',')]
            if len(parts) >= 3:
                result["street"] = parts[0]
                result["city"] = parts[1]
                state_zip = parts[2].split()
                if len(state_zip) >= 2:
                    result["state"] = state_zip[0]
                    result["zip"] = state_zip[1]
                elif len(state_zip) == 1:
                    result["state"] = state_zip[0]
            elif len(parts) == 2:
                result["street"] = parts[0]
                result["city"] = parts[1]
            return result

        # 2. Fallback for Comma-less/Normalized addresses
        # Format: STREET_PARTS CITY STATE ZIP
        parts = address.split()
        if len(parts) < 4:
            result["street"] = address
            return result
            
        # Zip is almost always last
        if parts[-1].isdigit() or '-' in parts[-1]:
            result["zip"] = parts.pop()
            
        # State is usually 2 letters after zip is gone
        if len(parts) >= 1 and len(parts[-1]) == 2:
            result["state"] = parts.pop()
            
        # For the remaining parts, it's Street + City. 
        # This is the hardest part. Usually City is 1 word in this context if commas are missing.
        # But we'll do our best:
        if len(parts) >= 2:
            result["city"] = parts.pop()
            result["street"] = " ".join(parts)
        else:
            result["street"] = " ".join(parts)
            
        return result

    def call_batchdata(self, address_str: str) -> Optional[Dict[str, Any]]:
        """Calls the BatchData Skip Trace API v1 (using v3-style payload supported by v1) for a single address."""
        if not self.api_key:
            logger.error("BATCHDATA_API_KEY is missing. Skipping call.")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        addr_parts = self.parse_address_string(address_str)
        
        payload = {
            "requests": [
                {
                    "propertyAddress": {
                        "street": addr_parts["street"],
                        "city": addr_parts["city"],
                        "state": addr_parts["state"],
                        "zip": addr_parts["zip"]
                    }
                }
            ]
        }
        
        try:
            logger.info(f"Calling BatchData v1 for: {address_str}")
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=15)
            # If 401/403, it's a config error, log critical
            if response.status_code in [401, 403]:
                logger.critical(f"BatchData Auth Error: {response.text}")
                return None
                
            return response.json()
        except Exception as e:
            logger.error(f"BatchData API v1 error: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def _acquire_next_property(self, priority_source: Optional[str] = None) -> Optional[Dict]:
        """
        ATOMIC lock acquisition - prevents race conditions.
        If priority_source is provided, tries to find a listing from that source first.
        """
        try:
            # 1. PRIORITY SOURCE ACQUISITION
            if priority_source:
                # We try a semi-atomic approach for the priority source
                now = datetime.now().isoformat()
                # Find one
                res = self.supabase.table("property_owner_enrichment_state") \
                    .select("*") \
                    .eq("status", "never_checked") \
                    .eq("locked", False) \
                    .eq("listing_source", priority_source) \
                    .limit(1) \
                    .execute()
                
                if res.data:
                    prop = res.data[0]
                    # Try to lock it specifically
                    lock_res = self.supabase.table("property_owner_enrichment_state") \
                        .update({"locked": True, "locked_at": now}) \
                        .eq("address_hash", prop['address_hash']) \
                        .eq("locked", False) \
                        .execute()
                    
                    if lock_res.data:
                        logger.info(f"Acquired PRIORITY lock for {priority_source}: {prop['address_hash'][:8]}")
                        return prop

            # 2. STANDARD ACQUISITION (RPC)
            # Atomically find and lock ONE unlocked property
            result = self.supabase.rpc('acquire_enrichment_lock').execute()
            
            if result.data and len(result.data) > 0:
                logger.info(f"Acquired lock for {result.data[0]['address_hash'][:8]}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return None

    def clear_stale_locks(self):
        """Unlock any properties that have been locked for more than 15 minutes but not processed."""
        fifteen_mins_ago = (datetime.now() - timedelta(minutes=15)).isoformat()
        try:
            # We look for never_checked properties that are locked and haven't been updated recently
            res = self.supabase.table("property_owner_enrichment_state") \
                .update({"locked": False}) \
                .eq("locked", True) \
                .eq("status", "never_checked") \
                .lt("updated_at", fifteen_mins_ago) \
                .execute()
            
            if res.data and len(res.data) > 0:
                logger.info(f"CLEARED {len(res.data)} stale locks (stuck in 'never_checked').")
        except Exception as e:
            logger.error(f"Error clearing stale locks: {e}")

    def run_enrichment(self, max_runs: int = 50, priority_source: Optional[str] = None):
        """Main loop to process pending enrichments with PAID-SAFE guarantees."""
        # Cleanup first
        self.clear_stale_locks()
        if not self.api_enabled and not self.dry_run:
            logger.warning("BatchData enrichment is DISABLED (BATCHDATA_ENABLED=false).")
            return

        # DRY RUN MODE - No API calls, no DB modifications
        if self.dry_run:
            self._run_dry_mode()
            return

        current_usage = self.check_daily_usage()
        remaining = self.daily_limit - current_usage
        
        if remaining <= 0:
            logger.warning(f"Daily limit reached ({current_usage}/{self.daily_limit}). "
                          f"Today's estimated cost: ${current_usage * self.cost_per_call:.2f}")
            return

        # Limit runs to remaining quota
        actual_runs = min(max_runs, remaining)
        logger.info(f"Starting enrichment. Usage: {current_usage}/{self.daily_limit}. "
                   f"Will process up to {actual_runs} properties.")

        processed = 0
        for _ in range(actual_runs):
            # Get and lock ONE property atomically
            prop = self._acquire_next_property(priority_source=priority_source)
            if not prop:
                logger.info("No more pending properties to process.")
                break
                
            self._process_single_property(prop)
            processed += 1
            
        # Final summary
        total_cost = (current_usage + processed) * self.cost_per_call
        logger.info(f"Enrichment complete. Processed: {processed}. "
                   f"Total API calls today: {current_usage + processed}. "
                   f"Estimated cost today: ${total_cost:.2f}")

    def _process_single_property(self, prop: Dict):
        """Process one property with proper state management."""
        address_hash = prop['address_hash']
        address = prop.get('normalized_address')
        listing_source = prop.get('listing_source')
        
        logger.info(f"Processing: {address} ({address_hash[:8]})")
        
        # PRE-FLIGHT CHECK: Validate listing still exists in source table
        # This prevents "Ghost" spending on deleted listings
        if not self._validate_listing_exists(listing_source, address_hash):
            logger.warning(f"SKIPPING: Listing {address_hash[:8]} not found in {listing_source}. likely deleted.")
            self._mark_no_data(address_hash, f"Orphaned: Not found in {listing_source}")
            return

        # SMART SKIP: Check if listing already has owner info (saves money!)
        existing_owner = self._check_existing_owner_info(listing_source, address_hash)
        if existing_owner:
            logger.info(f"SMART SKIP: {address_hash[:8]} already has owner '{existing_owner[:30]}...' - No API call needed!")
            # Copy existing owner info to property_owners table
            self._copy_existing_owner_to_central(listing_source, address_hash)
            self._mark_enriched_from_scrape(address_hash)
            return

        try:
            # Call BatchData API
            result = self.call_batchdata(address)
            
            # Check for API-level errors or success
            if result and result.get('status', {}).get('code') == 200:
                results_obj = result.get('results', {})
                persons_list = results_obj.get('persons', [])
                
                if not persons_list:
                    self._mark_no_data(address_hash, "No persons found in response")
                    return

                first_person = persons_list[0]
                
                # Check match confidence if available (optional)
                
                # Extract Data
                # Extract Owner Name
                # Priority 1: property.owner.name
                # Priority 2: first_person.name
                full_name = None
                owner_obj = first_person.get('property', {}).get('owner', {})
                if owner_obj:
                    o_name = owner_obj.get('name', {})
                    if o_name.get('first') or o_name.get('last'):
                        full_name = f"{o_name.get('first', '')} {o_name.get('last', '')}".strip()
                
                if not full_name:
                    p_name = first_person.get('name', {})
                    full_name = f"{p_name.get('first', '')} {p_name.get('last', '')}".strip()

                # Extract Mailing Address
                # Usually under property.owner.mailingAddress
                mailing_address = None
                mailing_obj = owner_obj.get('mailingAddress', {})
                if mailing_obj:
                    m_street = mailing_obj.get('street', '')
                    m_city = mailing_obj.get('city', '')
                    m_state = mailing_obj.get('state', '')
                    m_zip = mailing_obj.get('zip', '')
                    if m_street and m_city:
                        mailing_address = f"{m_street}, {m_city}, {m_state} {m_zip}".strip()

                # Extract Emails and Phones
                emails = [e.get('email') for e in first_person.get('emails', []) if e.get('email')]
                phones = [p.get('number') for p in first_person.get('phoneNumbers', []) if p.get('number')] # v1 uses phoneNumbers

                email = emails[0] if emails else None
                phone = phones[0] if phones else None
                
                clean_name, clean_email, clean_phone = clean_owner_data(full_name, email, phone)
                
                # Check if we have enough data to count as enriched
                # Now we really want mailing address too.
                # If we have clean_name AND (email OR phone OR mailing_address) -> consider success?
                # User said: "Upsert owner_name, email, phone, mailing_address". 
                # And "if owner data found (including mailing address ideally): status='enriched'"
                
                if any([clean_name, clean_email, clean_phone, mailing_address]):
                    # SUCCESS WITH DATA
                    owner_data = {
                        "owner_name": clean_name or full_name, 
                        "owner_email": clean_email,
                        "owner_phone": clean_phone,
                        "mailing_address": mailing_address
                    }
                    self._save_enriched_data(address_hash, owner_data, result, listing_source)
                    self._mark_enriched(address_hash, result)
                    logger.info(f"Enriched: {address_hash[:8]}")
                else:
                    # SUCCESS BUT NO DATA FOUND (after cleaning)
                    self._mark_no_data(address_hash, "No valid contact info or mailing address after cleaning")
                    
            else:
                # API ERROR or no result
                error_msg = result.get('status', {}).get('text', 'Unknown API error') if result else 'No response from API'
                self._mark_failed(address_hash, f"API error: {error_msg}")
                logger.error(f"Enrichment failed: {address_hash[:8]} - {error_msg}")
                
        except Exception as e:
            # ANY EXCEPTION - Mark as failed (terminal)
            # This is critical for cost safety - do not infinite retry on crash
            self._mark_failed(address_hash, f"Exception: {str(e)[:200]}")
            logger.exception(f"Exception processing {address_hash[:8]}")

    def _save_enriched_data(self, address_hash: str, owner_data: Dict, raw_response: Dict, listing_source: str):
        # Save to central owner table
        payload = {
            "address_hash": address_hash,
            "owner_name": owner_data.get('owner_name'),
            "owner_email": owner_data.get('owner_email'),
            "owner_phone": owner_data.get('owner_phone'),
            "mailing_address": owner_data.get('mailing_address'),
            "source": "batchdata",
            "listing_source": listing_source,
        }
        self.supabase.table("property_owners").upsert(payload, on_conflict="address_hash").execute()

        # SYNC BACK to source listing table if possible
        try:
            # Map various source name formats to table names
            source_lower = listing_source.lower() if listing_source else ""
            
            source_map = {
                'fsbo': 'listings',
                'forsalebyowner': 'listings',
                'zillow-fsbo': 'zillow_fsbo_listings',
                'zillow fsbo': 'zillow_fsbo_listings',
                'zillow-frbo': 'zillow_frbo_listings',
                'zillow frbo': 'zillow_frbo_listings',
                'hotpads': 'hotpads_listings',
                'apartments': 'apartments_frbo_chicago',
                'apartments.com': 'apartments_frbo_chicago',
                'trulia': 'trulia_listings',
                'redfin': 'redfin_listings'
            }
            
            target_table = source_map.get(source_lower)
            if target_table:
                update_payload = {
                    "owner_name": owner_data.get('owner_name')
                }
                
                # Only add mailing_address if the table has that column
                # Based on schema dump:
                # listings, trulia_listings, redfin_listings have mailing_address
                if target_table in ['listings', 'trulia_listings', 'redfin_listings']:
                    update_payload["mailing_address"] = owner_data.get('owner_address') or owner_data.get('mailing_address')

                # Special handling for tables with specific column names or types
                if target_table == 'listings':
                    # listings table uses JSONB arrays for emails and phones
                    if owner_data.get('owner_email'):
                        update_payload["owner_emails"] = [owner_data.get('owner_email')]
                    if owner_data.get('owner_phone'):
                        update_payload["owner_phones"] = [owner_data.get('owner_phone')]
                
                elif target_table in ['zillow_fsbo_listings', 'zillow_frbo_listings']:
                    # These tables use 'phone_number' column and 'owner_email'
                    if owner_data.get('owner_phone'):
                        update_payload["phone_number"] = owner_data.get('owner_phone')
                    if owner_data.get('owner_email'):
                        update_payload["owner_email"] = owner_data.get('owner_email')
                
                elif target_table == 'apartments_frbo_chicago':
                    # Has owner_email, owner_name, and phone_numbers (list)
                    if owner_data.get('owner_email'):
                        update_payload["owner_email"] = owner_data.get('owner_email')
                    if owner_data.get('owner_phone'):
                        update_payload["phone_numbers"] = [owner_data.get('owner_phone')]
                
                elif target_table == 'hotpads_listings':
                    # Has email, owner_name, owner_phone, phone_number
                    if owner_data.get('owner_email'):
                        update_payload["email"] = owner_data.get('owner_email')
                    if owner_data.get('owner_phone'):
                        update_payload["owner_phone"] = owner_data.get('owner_phone')
                        update_payload["phone_number"] = owner_data.get('owner_phone')

                elif target_table in ['trulia_listings', 'redfin_listings']:
                    # These tables use 'emails' (string/list) and 'phones' (string/list)
                    if owner_data.get('owner_email'):
                        update_payload["emails"] = owner_data.get('owner_email')
                    if owner_data.get('owner_phone'):
                        update_payload["phones"] = owner_data.get('owner_phone')
                
                # Update the source record using address_hash as key
                self.supabase.table(target_table).update(update_payload).eq("address_hash", address_hash).execute()
                logger.info(f"Synced back enriched data to {target_table} for {address_hash[:8]}")
                
        except Exception as e:
            logger.warning(f"Failed to sync back enriched data to {listing_source}: {e}")
            # Don't fail the whole enrichment if sync-back fails

    def _mark_enriched(self, address_hash: str, raw_response: Dict):
        req_id = raw_response.get('results', {}).get('meta', {}).get('requestId')
        self.supabase.table("property_owner_enrichment_state").update({
            "status": "enriched",
            "locked": True,
            "checked_at": datetime.now().isoformat(),
            "source_used": "batchdata",
            "batchdata_request_id": req_id
        }).eq("address_hash", address_hash).execute()

    def _mark_no_data(self, address_hash: str, reason: str = "No data"):
        """Terminal state for no data found"""
        self.supabase.table("property_owner_enrichment_state").update({
            "status": "no_owner_data",
            "locked": True,
            "failure_reason": reason,
            "checked_at": datetime.now().isoformat(),
            "source_used": "batchdata"
        }).eq("address_hash", address_hash).execute()

    def _mark_failed(self, address_hash: str, reason: str):
        """
        TERMINAL STATE - Property will NEVER be retried.
        This is critical for cost safety.
        """
        self.supabase.table("property_owner_enrichment_state").update({
            "status": "failed",  # TERMINAL - no retry
            "locked": False, # Technically false so we could inspect it, but status 'failed' prevents pickup
            "failure_reason": reason[:500],
            "source_used": "batchdata",
            "checked_at": datetime.now().isoformat()
        }).eq("address_hash", address_hash).execute()
        logger.warning(f"TERMINAL FAIL: {address_hash[:8]} - {reason}")

    def _validate_listing_exists(self, listing_source: str, address_hash: str) -> bool:
        """
        PRE-FLIGHT CHECK: Verify listing still exists in source table.
        Returns True if listing exists, False if orphaned.
        This prevents wasting money on deleted listings.
        """
        if not listing_source:
            return True  # Unknown source, allow to proceed
            
        source_lower = listing_source.lower()
        source_map = {
            'fsbo': 'listings',
            'forsalebyowner': 'listings',
            'zillow-fsbo': 'zillow_fsbo_listings',
            'zillow fsbo': 'zillow_fsbo_listings',
            'zillow-frbo': 'zillow_frbo_listings',
            'zillow frbo': 'zillow_frbo_listings',
            'hotpads': 'hotpads_listings',
            'apartments': 'apartments_frbo_chicago',
            'apartments.com': 'apartments_frbo_chicago',
            'trulia': 'trulia_listings',
            'redfin': 'redfin_listings'
        }
        
        target_table = source_map.get(source_lower)
        if not target_table:
            logger.warning(f"Unknown source '{listing_source}', allowing enrichment")
            return True
            
        try:
            result = self.supabase.table(target_table) \
                .select("id") \
                .eq("address_hash", address_hash) \
                .limit(1) \
                .execute()
            
            exists = len(result.data) > 0
            if not exists:
                logger.info(f"Pre-flight check: {address_hash[:8]} NOT FOUND in {target_table}")
            return exists
        except Exception as e:
            logger.error(f"Pre-flight check error: {e}")
            return True  # On error, allow to proceed (fail-safe)

    def _check_existing_owner_info(self, listing_source: str, address_hash: str) -> Optional[str]:
        """
        SMART SKIP: Check if source table already has owner info.
        Returns owner_name if exists, None otherwise.
        """
        if not listing_source:
            return None
            
        source_lower = listing_source.lower()
        source_map = {
            'fsbo': ('listings', 'owner_name'),
            'forsalebyowner': ('listings', 'owner_name'),
            'zillow-fsbo': ('zillow_fsbo_listings', 'owner_name'),
            'zillow fsbo': ('zillow_fsbo_listings', 'owner_name'),
            'zillow-frbo': ('zillow_frbo_listings', 'owner_name'),
            'zillow frbo': ('zillow_frbo_listings', 'owner_name'),
            'hotpads': ('hotpads_listings', 'owner_name'),
            'apartments': ('apartments_frbo_chicago', 'owner_name'),
            'apartments.com': ('apartments_frbo_chicago', 'owner_name'),
            'trulia': ('trulia_listings', 'owner_name'),
            'redfin': ('redfin_listings', 'owner_name')
        }
        
        table_info = source_map.get(source_lower)
        if not table_info:
            return None
            
        target_table, owner_col = table_info
        
        try:
            result = self.supabase.table(target_table) \
                .select(owner_col) \
                .eq("address_hash", address_hash) \
                .limit(1) \
                .execute()
            
            if result.data and result.data[0].get(owner_col):
                owner_name = result.data[0][owner_col]
                if owner_name and owner_name.strip() and owner_name.lower() not in ['n/a', 'unknown', 'none', '']:
                    return owner_name
            return None
        except Exception as e:
            logger.error(f"Smart skip check error: {e}")
            return None

    def _copy_existing_owner_to_central(self, listing_source: str, address_hash: str):
        """
        Copy existing owner info from source table to central property_owners table.
        """
        source_lower = listing_source.lower() if listing_source else ""
        
        # Map sources to tables and their column names
        source_map = {
            'fsbo': 'listings',
            'forsalebyowner': 'listings',
            'zillow-fsbo': 'zillow_fsbo_listings',
            'zillow fsbo': 'zillow_fsbo_listings',
            'zillow-frbo': 'zillow_frbo_listings',
            'zillow frbo': 'zillow_frbo_listings',
            'hotpads': 'hotpads_listings',
            'apartments': 'apartments_frbo_chicago',
            'apartments.com': 'apartments_frbo_chicago',
            'trulia': 'trulia_listings',
            'redfin': 'redfin_listings'
        }
        
        target_table = source_map.get(source_lower)
        if not target_table:
            return
            
        try:
            # Fetch existing owner data from source
            result = self.supabase.table(target_table) \
                .select("*") \
                .eq("address_hash", address_hash) \
                .limit(1) \
                .execute()
            
            if not result.data:
                return
                
            row = result.data[0]
            
            # Extract owner info based on table structure
            owner_name = row.get('owner_name')
            owner_email = row.get('owner_email') or row.get('email')
            owner_phone = row.get('owner_phone') or row.get('phone_number')
            
            # For listings table, emails/phones might be arrays
            if target_table == 'listings':
                emails = row.get('owner_emails', [])
                phones = row.get('owner_phones', [])
                if emails and isinstance(emails, list) and len(emails) > 0:
                    owner_email = emails[0]
                if phones and isinstance(phones, list) and len(phones) > 0:
                    owner_phone = phones[0]
            
            # Save to central property_owners table
            payload = {
                "address_hash": address_hash,
                "owner_name": owner_name,
                "owner_email": owner_email,
                "owner_phone": owner_phone,
                "source": "scraped",  # Indicate this came from original scrape, not BatchData
                "listing_source": listing_source
            }
            self.supabase.table("property_owners").upsert(payload, on_conflict="address_hash").execute()
            logger.info(f"Copied existing owner to central: {address_hash[:8]}")
            
        except Exception as e:
            logger.error(f"Error copying existing owner: {e}")

    def _mark_enriched_from_scrape(self, address_hash: str):
        """Mark as enriched but note that data came from original scrape, not API."""
        self.supabase.table("property_owner_enrichment_state").update({
            "status": "enriched",
            "locked": True,
            "checked_at": datetime.now().isoformat(),
            "source_used": "scraped"  # Different from 'batchdata' - indicates no API cost
        }).eq("address_hash", address_hash).execute()

    def _run_dry_mode(self):
        """
        DRY RUN MODE - For cost estimation.
        NO API calls. NO database modifications.
        """
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - No API calls or DB changes will be made")
        logger.info("=" * 60)
        
        # Count eligible properties using head=True to get exact count without fetching all rows
        # This avoids the default 1000 row limit
        result = self.supabase.table("property_owner_enrichment_state") \
            .select("*", count="exact", head=True) \
            .eq("status", "never_checked") \
            .eq("locked", False) \
            .execute()
        
        count = result.count
        estimated_cost = count * self.cost_per_call
        
        logger.info(f"\nEligible properties for enrichment: {count}")
        logger.info(f"Estimated cost if processed: ${estimated_cost:.2f}")
        logger.info(f"Cost per call: ${self.cost_per_call}")
        
        if count > 0:
            logger.info("\nSample of eligible properties:")
            # Fetch a small sample to display
            sample_res = self.supabase.table("property_owner_enrichment_state") \
                .select("address_hash, normalized_address, listing_source") \
                .eq("status", "never_checked") \
                .eq("locked", False) \
                .limit(10) \
                .execute()
                
            sample = sample_res.data or []
            for i, prop in enumerate(sample):
                logger.info(f"  {i+1}. {prop['address_hash'][:16]}... | {prop.get('listing_source', 'Unknown')} | {prop['normalized_address'][:50]}...")
            
            if count > 10:
                logger.info(f"  ... and {count - 10} more")
        
        logger.info("=" * 60)
        logger.info("DRY RUN COMPLETE - No changes made")
        logger.info("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run BatchData Enrichment")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of properties to process")
    parser.add_argument("--source", type=str, default=None, help="Priority source to process first (e.g. Trulia)")
    args = parser.parse_args()

    worker = BatchDataWorker()
    worker.run_enrichment(max_runs=args.limit, priority_source=args.source)
