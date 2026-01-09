"""
Script to reassign the 3 records to specific IDs: 134, 135, 136.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
project_root = Path(__file__).parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Get Supabase credentials
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: Supabase credentials not found")
    exit(1)

try:
    supabase = create_client(supabase_url, supabase_key)
    
    print("=" * 70)
    print("Reassigning records to IDs 134, 135, 136")
    print("=" * 70)
    
    # Get the 3 records we just inserted (should be 1026, 1027, 1028)
    print("\n1. Finding the records to reassign...")
    target_ids = [1026, 1027, 1028]
    records_to_fix = []
    
    for target_id in target_ids:
        try:
            result = supabase.table("listings").select("*").eq("id", target_id).execute()
            if result.data and len(result.data) > 0:
                records_to_fix.append(result.data[0])
                print(f"   [OK] Found record with ID {target_id}: {result.data[0].get('address', 'N/A')[:50]}")
            else:
                print(f"   [WARN] No record found with ID {target_id}")
        except Exception as e:
            print(f"   [ERROR] Could not check ID {target_id}: {e}")
    
    if len(records_to_fix) != 3:
        print(f"\n[ERROR] Expected 3 records, found {len(records_to_fix)}")
        exit(1)
    
    # Check if IDs 134, 135, 136 are already taken
    print("\n2. Checking if target IDs (134, 135, 136) are available...")
    target_new_ids = [134, 135, 136]
    conflicts = []
    
    for new_id in target_new_ids:
        try:
            result = supabase.table("listings").select("id").eq("id", new_id).execute()
            if result.data and len(result.data) > 0:
                conflicts.append(new_id)
                print(f"   [CONFLICT] ID {new_id} is already taken by: {result.data[0].get('address', 'N/A')[:50]}")
            else:
                print(f"   [OK] ID {new_id} is available")
        except Exception as e:
            print(f"   [ERROR] Could not check ID {new_id}: {e}")
    
    if conflicts:
        print(f"\n[ERROR] Cannot proceed: IDs {conflicts} are already taken")
        print("Please free up these IDs first, or choose different target IDs.")
        exit(1)
    
    print("\n3. Reassigning records...")
    print("   Method: Delete from current IDs, re-insert with explicit IDs")
    print("   Note: This requires temporarily adjusting the sequence")
    print()
    
    # We need to use SQL to directly set the IDs
    # Since Supabase Python client doesn't easily support this, we'll provide SQL commands
    # But first, let's try a workaround: delete and re-insert with sequence manipulation
    
    print("=" * 70)
    print("SQL COMMANDS TO FIX IDs")
    print("=" * 70)
    print("\nRun these SQL commands in Supabase SQL Editor (in order):\n")
    
    # First, get the record data to generate UPDATE statements
    for i, record in enumerate(records_to_fix):
        old_id = record['id']
        new_id = target_new_ids[i]
        listing_link = record.get('listing_link', '')
        address = record.get('address', 'N/A')
        
        print(f"-- Fix record: {address[:50]}")
        print(f"-- Old ID: {old_id}, New ID: {new_id}")
        
        # Generate UPDATE SQL
        # We need to update the ID directly, but this requires careful handling
        print(f"""
-- Step 1: Delete the record with ID {old_id}
DELETE FROM listings WHERE id = {old_id};

-- Step 2: Temporarily set sequence to allow inserting at {new_id}
SELECT setval('listings_id_seq', {new_id - 1}, false);

-- Step 3: Re-insert with explicit ID {new_id}
INSERT INTO listings (id, listing_link, address, price, beds, baths, square_feet, time_of_post, owner_emails, owner_phones, owner_name, mailing_address)
VALUES (
    {new_id},
    '{listing_link.replace("'", "''")}',
    '{record.get('address', '').replace("'", "''")}',
    {f"'{record.get('price', '').replace("'", "''")}'" if record.get('price') else 'NULL'},
    {f"'{record.get('beds', '').replace("'", "''")}'" if record.get('beds') else 'NULL'},
    {f"'{record.get('baths', '').replace("'", "''")}'" if record.get('baths') else 'NULL'},
    {f"'{record.get('square_feet', '').replace("'", "''")}'" if record.get('square_feet') else 'NULL'},
    {f"'{record.get('time_of_post', '').replace("'", "''")}'" if record.get('time_of_post') else 'NULL'},
    {f"'{str(record.get('owner_emails', '[]'))}'::jsonb" if record.get('owner_emails') else 'NULL'},
    {f"'{str(record.get('owner_phones', '[]'))}'::jsonb" if record.get('owner_phones') else 'NULL'},
    {f"'{record.get('owner_name', '').replace("'", "''")}'" if record.get('owner_name') else 'NULL'},
    {f"'{record.get('mailing_address', '').replace("'", "''")}'" if record.get('mailing_address') else 'NULL'}
);
""")
    
    print("\n" + "=" * 70)
    print("After running all SQL commands above, run this to fix the sequence:")
    print("=" * 70)
    print("\nSELECT setval('listings_id_seq', (SELECT MAX(id) FROM listings));\n")
    print("=" * 70)
    
    print("\n[INFO] The SQL commands above will:")
    print("1. Delete each record from its current ID (1026, 1027, 1028)")
    print("2. Set the sequence to allow inserting at the target ID")
    print("3. Re-insert the record with the target ID (134, 135, 136)")
    print("4. Reset the sequence to the correct max ID")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

