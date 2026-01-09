"""
Check current state of listings table to see what happened.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

project_root = Path(__file__).parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: Supabase credentials not found")
    exit(1)

try:
    supabase = create_client(supabase_url, supabase_key)
    
    print("=" * 70)
    print("Checking current state of listings table")
    print("=" * 70)
    
    # Check for IDs 1026, 1027, 1028
    print("\n1. Checking for records with IDs 1026, 1027, 1028...")
    for check_id in [1026, 1027, 1028]:
        result = supabase.table("listings").select("*").eq("id", check_id).execute()
        if result.data and len(result.data) > 0:
            print(f"   [FOUND] ID {check_id}: {result.data[0].get('address', 'N/A')[:50]}")
        else:
            print(f"   [NOT FOUND] ID {check_id}")
    
    # Check for IDs 134, 135, 136
    print("\n2. Checking for records with IDs 134, 135, 136...")
    for check_id in [134, 135, 136]:
        result = supabase.table("listings").select("*").eq("id", check_id).execute()
        if result.data and len(result.data) > 0:
            print(f"   [FOUND] ID {check_id}: {result.data[0].get('address', 'N/A')[:50]}")
        else:
            print(f"   [AVAILABLE] ID {check_id}")
    
    # Get the last 5 records
    print("\n3. Last 5 records by ID:")
    result = supabase.table("listings").select("id, address, listing_link").order("id", desc=True).limit(5).execute()
    if result.data:
        for record in result.data:
            print(f"   ID {record['id']}: {record.get('address', 'N/A')[:50]}")
    else:
        print("   No records found")
    
    # Check for the specific addresses we're looking for
    print("\n4. Searching for the 3 addresses by listing_link...")
    addresses_to_find = [
        "6236 North Ridgeway Avenue",
        "1008 West 115Th Street", 
        "5338 South Wabash Avenue"
    ]
    
    for address in addresses_to_find:
        result = supabase.table("listings").select("id, address, listing_link").ilike("address", f"%{address.split()[0]}%").limit(5).execute()
        if result.data:
            for record in result.data:
                if any(addr_part in record.get('address', '') for addr_part in address.split()[:3]):
                    print(f"   [FOUND] {record.get('address', 'N/A')[:50]} - ID: {record['id']}")
                    break
        else:
            print(f"   [NOT FOUND] {address}")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

