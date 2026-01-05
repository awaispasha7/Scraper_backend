import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def verify_all_columns():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    tables = [
        'listings', 
        'zillow_fsbo_listings', 
        'zillow_frbo_listings', 
        'hotpads_listings', 
        'apartments_frbo', 
        'trulia_listings', 
        'redfin_listings'
    ]
    
    for t in tables:
        try:
            res = supabase.table(t).select('*').limit(1).execute()
            if res.data:
                cols = sorted(res.data[0].keys())
                print(f"--- {t} ---")
                for c in cols:
                    if any(x in c.lower() for x in ['owner', 'mail', 'email', 'phone', 'hash', 'address']):
                        print(f"  {c}")
            else:
                print(f"--- {t} (No data) ---")
        except Exception as e:
            print(f"--- {t} (Error: {e}) ---")

if __name__ == "__main__":
    verify_all_columns()
