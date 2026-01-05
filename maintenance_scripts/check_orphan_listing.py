import os
import time
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

TABLES = [
    'listings', 
    'zillow_fsbo_listings', 
    'zillow_frbo_listings', 
    'hotpads_listings', 
    'apartments_frbo', 
    'trulia_listings', 
    'redfin_listings'
]

def check_listing():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    addr = '4701 SOUTH CALUMET'
    print(f"Searching for partial address: {addr}...")
    
    found = False
    for t in TABLES:
        try:
            res = supabase.table(t).select('address').ilike('address', f'%{addr}%').execute()
            if res.data:
                print(f"FOUND in {t}: {res.data}")
                found = True
        except Exception as e:
            print(f"Error checking {t}: {e}")
            
    if not found:
        print("NOT FOUND in any table.")

if __name__ == '__main__':
    check_listing()
