import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def inspect_fairside():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # New Standard Hash for 1809 Fairside
    new_hash = '06d25fd407afe9addf4b59ff902c1e16'
    # Old raw hash we found earlier
    old_hash = 'bde3c236ca815fdbc9c1c00307bd5afe'
    
    print(f"--- Enrichment State ---")
    res = supabase.table('property_owner_enrichment_state').select('*').in_('address_hash', [new_hash, old_hash]).execute()
    for row in res.data:
        print(f"ID: {row['id']}")
        print(f"Hash: {row['address_hash']}")
        print(f"Status: {row['status']}")
        print(f"Original: {row.get('original_address')}")
        print(f"Normalized: {row.get('normalized_address')}")
        print("-" * 20)
        
    print(f"\n--- Property Owners ---")
    res = supabase.table('property_owners').select('address_hash, owner_name').in_('address_hash', [new_hash, old_hash]).execute()
    for row in res.data:
        print(f"Hash: {row['address_hash']}")
        print(f"Owner: {row['owner_name']}")
        print("-" * 20)

if __name__ == '__main__':
    inspect_fairside()
