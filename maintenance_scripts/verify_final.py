import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def verify_final():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # Standard Hash for 1809 Fairside
    hash_val = '06d25fd407afe9addf4b59ff902c1e16'
    
    print(f"--- Enrichment State ---")
    res = supabase.table('property_owner_enrichment_state').select('address_hash, status, listing_source').eq('address_hash', hash_val).execute()
    print(res.data)
        
    print(f"\n--- Property Owners ---")
    res = supabase.table('property_owners').select('address_hash, owner_name').eq('address_hash', hash_val).execute()
    print(res.data)
    
    print(f"\n--- Zillow FSBO Listings ---")
    res = supabase.table('zillow_fsbo_listings').select('address, address_hash, owner_name, phone_number').eq('address_hash', hash_val).execute()
    print(res.data)

if __name__ == '__main__':
    verify_final()
