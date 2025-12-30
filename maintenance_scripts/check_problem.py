import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_problematic_property():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    addr = '4800 S Lake Park'
    
    print(f"Checking for address: {addr}")
    
    # 1. Check zillow_fsbo_listings
    print("\n--- Zillow FSBO ---")
    res = supabase.table('zillow_fsbo_listings').select('*').ilike('address', f'%{addr}%').execute()
    if res.data:
        for item in res.data:
            print(f"Address: {item.get('address')}")
            print(f"Hash:    {item.get('address_hash')}")
            print(f"Owner:   {item.get('owner_name')}")
            print(f"Email:   {item.get('owner_email') or item.get('emails')}")
            print(f"Phone:   {item.get('phone_number') or item.get('phones')}")
    else:
        print("Not found in zillow_fsbo_listings.")
        
    # 2. Check property_owner_enrichment_state
    print("\n--- Enrichment State ---")
    # Search for LAKE PARK normalized
    res = supabase.table('property_owner_enrichment_state').select('*').ilike('normalized_address', f'%LAKE PARK%').execute()
    if res.data:
        for item in res.data:
            if '2107' in item['normalized_address']:
                print(f"Address: {item['normalized_address']}")
                print(f"Hash:    {item['address_hash']}")
                print(f"Status:  {item['status']}")
    else:
        print("Not found in property_owner_enrichment_state.")
        
    # 3. Check property_owners
    print("\n--- Property Owners ---")
    # Search by address_hash if found above, or by mailing address
    res = supabase.table('property_owners').select('*').ilike('owner_name', '%').execute() # Too many, let's just search by hash if we get it
    
    # Let's try to get the hash from step 1 or 2
    hashes = []
    if res.data: # This is just a placeholder, I'll use the hashes from above
        pass
        
    # Better: Search property_owners by address_hash if we found any in Step 1 or 2
    found_hashes = set()
    if 'listings' in locals() or True: # Just for structure
        pass
        
if __name__ == '__main__':
    check_problematic_property()
