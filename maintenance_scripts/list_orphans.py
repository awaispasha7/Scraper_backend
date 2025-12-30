import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def list_orphans():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    res = supabase.table('property_owner_enrichment_state').select('id, address_hash, normalized_address').eq('status', 'orphaned').limit(10).execute()
    print(json.dumps(res.data, indent=2))

if __name__ == '__main__':
    list_orphans()
