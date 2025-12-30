import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_specific_hash():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # MD5 of '5338 south wabash avenue chicago il 60615'
    target = '0ca45f65f17d3d043477e3c155d8f0f0'
    
    TABLES = [
        'listings', 
        'zillow_fsbo_listings', 
        'zillow_frbo_listings', 
        'hotpads_listings', 
        'apartments_frbo_chicago', 
        'trulia_listings', 
        'redfin_listings', 
        'property_owners', 
        'property_owner_enrichment_state'
    ]
    
    print(f"Searching for hash: {target}")
    found = False
    for t in TABLES:
        res = supabase.table(t).select('*').eq('address_hash', target).execute()
        if res.data:
            print(f"✅ Found in {t}: {len(res.data)} records")
            found = True
            
    if not found:
        print("❌ Not found in any table.")

if __name__ == '__main__':
    check_specific_hash()
