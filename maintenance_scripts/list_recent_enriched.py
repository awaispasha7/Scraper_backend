import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def list_recent():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    supabase = create_client(url, key)
    
    # Simple fetch of just address
    res = supabase.table('property_owner_enrichment_state') \
        .select('normalized_address') \
        .eq('status', 'enriched') \
        .order('checked_at', desc=True) \
        .limit(5) \
        .execute()
        
    print("Most Recent Enriched Addresses:")
    print("-" * 30)
    for r in res.data:
        print(f"• {r.get('normalized_address')}")
    print("-" * 30)

if __name__ == '__main__':
    list_recent()
