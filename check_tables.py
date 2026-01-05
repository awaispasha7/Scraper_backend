import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_tables():
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
                print(f"\nTable: {t}")
                print(f"Columns: {list(res.data[0].keys())}")
            else:
                print(f"\nTable: {t} (No data)")
                # If no data, we can't easily see columns this way, but we can try to find another row or use a different method if needed.
        except Exception as e:
            print(f"\nTable: {t} - Error: {e}")

if __name__ == "__main__":
    check_tables()
