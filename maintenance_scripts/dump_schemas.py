import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def dump_schemas():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    supabase = create_client(url, key)
    
    tables = [
        'listings', 
        'zillow_fsbo_listings', 
        'zillow_frbo_listings', 
        'hotpads_listings', 
        'apartments_frbo_chicago', 
        'trulia_listings', 
        'redfin_listings'
    ]
    
    schemas = {}
    for t in tables:
        try:
            res = supabase.table(t).select('*').limit(1).execute()
            if res.data:
                schemas[t] = sorted(res.data[0].keys())
            else:
                schemas[t] = "No data"
        except Exception as e:
            schemas[t] = f"Error: {e}"
            
    with open('schemas.json', 'w') as f:
        json.dump(schemas, f, indent=2)
    print("Schemas dumped to schemas.json")

if __name__ == "__main__":
    dump_schemas()
