import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def debug_api():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # 1. Fetch attempts (Limit 5)
    res_attempts = supabase.table('property_owner_enrichment_state') \
        .select('address_hash, normalized_address, status, checked_at, listing_source') \
        .not_.is_('checked_at', 'null') \
        .order('checked_at', desc=True) \
        .limit(5) \
        .execute()
        
    attempts = res_attempts.data
    print(f"Attempts: {len(attempts)}")
    
    hashes = [a['address_hash'] for a in attempts]
    
    # 2. Fetch owners
    if hashes:
        res_owners = supabase.table('property_owners') \
            .select('address_hash, owner_name') \
            .in_('address_hash', hashes) \
            .execute()
        owners = res_owners.data
        print(f"Owners: {len(owners)}")
        
        owner_map = {o['address_hash']: o for o in owners}
        
        for a in attempts:
            h = a['address_hash']
            addr = a['normalized_address'][:30] # Limit length
            
            if h in owner_map:
                print(f"[OK] {addr} -> Owner: {owner_map[h]['owner_name']}")
            else:
                print(f"[MISSING] {addr} -> Hash: {h[:8]}...")

if __name__ == '__main__':
    debug_api()
