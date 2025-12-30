import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def dump_orphans():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    res = supabase.table('property_owner_enrichment_state').select('*').eq('status', 'orphaned').limit(20).execute()
    
    with open('orphans_dump.json', 'w') as f:
        json.dump(res.data, f, indent=2)
    
    print(f"Dumped {len(res.data)} orphans to orphans_dump.json")

if __name__ == '__main__':
    dump_orphans()
