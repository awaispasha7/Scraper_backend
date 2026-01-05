import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_address():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    TABLES = [
        'listings', 
        'zillow_fsbo_listings', 
        'zillow_frbo_listings', 
        'hotpads_listings', 
        'apartments_frbo', 
        'trulia_listings', 
        'redfin_listings'
    ]
    addr = '10212 1/2 S Malta St'
    
    print(f"Searching for address: {addr}")
    found = False
    for t in TABLES:
        try:
            res = supabase.table(t).select('address, address_hash').ilike('address', f'%{addr}%').execute()
            if res.data:
                print(f"✅ Found in {t}:")
                for item in res.data:
                    print(f"  - Address: {item['address']}")
                    print(f"  - Hash:    {item['address_hash']}")
                found = True
        except Exception as e:
            print(f"❌ Error checking {t}: {e}")
            
    if not found:
        print("❌ Not found in any listing table.")
        
    # Check enrichment state
    print("\nChecking enrichment state:")
    try:
        res = supabase.table('property_owner_enrichment_state').select('*').ilike('normalized_address', f'%MALTA%').execute()
        if res.data:
            for item in res.data:
                print(f"  - Address: {item['normalized_address']}")
                print(f"  - Hash:    {item['address_hash']}")
                print(f"  - Status:  {item['status']}")
                print(f"  - Source:  {item['listing_source']}")
        else:
            print("  - No record found in enrichment state.")
    except Exception as e:
        print(f"❌ Error checking enrichment state: {e}")

if __name__ == '__main__':
    check_address()
