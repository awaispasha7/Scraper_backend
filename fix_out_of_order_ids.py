"""
Script to fix the last 3 out-of-order IDs in the listings table.
This will reassign sequential IDs to records that are out of order.

Safe method: Delete and re-insert the affected records (they'll get new sequential IDs).
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
    print("ERROR: Supabase credentials not found in environment variables")
    print("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env file")
    exit(1)

try:
    supabase = create_client(supabase_url, supabase_key)
    
    print("=" * 70)
    print("Fixing out-of-order IDs in listings table")
    print("=" * 70)
    
    # Get the last 3 records ordered by ID descending
    print("\n1. Finding records with out-of-order IDs...")
    try:
        result = supabase.table("listings").select("*").order("id", desc=True).limit(3).execute()
        
        if not result.data or len(result.data) < 3:
            print("   [WARN] Not enough records to fix (need at least 3)")
            exit(1)
        
        records = result.data
        print(f"   [OK] Found {len(records)} records to check:")
        print()
        
        for i, record in enumerate(records, 1):
            print(f"   Record {i}:")
            print(f"      ID: {record.get('id')}")
            print(f"      Address: {record.get('address', 'N/A')}")
            print(f"      Listing Link: {record.get('listing_link', 'N/A')[:60]}...")
            print()
        
        # Get the maximum ID that should be used
        max_id_result = supabase.table("listings").select("id").order("id", desc=True).limit(1).execute()
        current_max_id = max_id_result.data[0]['id'] if max_id_result.data else 0
        
        # Get all IDs to find what the next sequential IDs should be
        all_ids_result = supabase.table("listings").select("id").order("id", desc=True).execute()
        all_ids = sorted([r['id'] for r in all_ids_result.data], reverse=True)
        
        print(f"2. Current situation:")
        print(f"   Maximum ID in table: {current_max_id}")
        print(f"   Top 3 IDs: {[r['id'] for r in records]}")
        print()
        
        # Find what the next sequential IDs should be
        # Start from the 4th highest ID and count up
        if len(all_ids) > 3:
            base_id = all_ids[3]  # The 4th highest ID
        else:
            base_id = 0
        
        # Calculate what IDs these 3 records should have
        new_ids = [base_id + 1, base_id + 2, base_id + 3]
        old_ids = [r['id'] for r in records]
        
        print(f"3. Proposed fix:")
        print(f"   These 3 records should have IDs: {new_ids}")
        print(f"   Instead of current IDs: {old_ids}")
        print()
        
        # Auto-proceed (can be made interactive if needed)
        print("=" * 70)
        print("Auto-fixing IDs (use --interactive flag for confirmation prompt)")
        import sys
        if '--interactive' in sys.argv:
            response = input("Do you want to fix these IDs? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled.")
                exit(0)
        
        print("\n4. Fixing IDs...")
        print("   Method: Re-insert records with correct sequential IDs")
        print()
        
        # For each record, we'll delete it and re-insert it
        # This ensures it gets a new sequential ID
        fixed_count = 0
        for i, record in enumerate(records):
            old_id = record['id']
            listing_link = record.get('listing_link')
            
            if not listing_link:
                print(f"   [SKIP] Record {old_id}: No listing_link, cannot safely re-insert")
                continue
            
            try:
                # Remove auto-generated fields
                record.pop('id', None)
                record.pop('created_at', None)
                record.pop('updated_at', None)
                
                # Delete the old record
                print(f"   [DELETE] Removing record with ID {old_id}...")
                delete_result = supabase.table("listings").delete().eq("id", old_id).execute()
                
                # Re-insert the record (it will get a new sequential ID)
                print(f"   [INSERT] Re-inserting record (will get new sequential ID)...")
                insert_result = supabase.table("listings").insert(record).execute()
                
                if insert_result.data:
                    new_id = insert_result.data[0].get('id')
                    print(f"   [SUCCESS] Record re-inserted with new ID: {new_id}")
                    fixed_count += 1
                else:
                    print(f"   [ERROR] Failed to re-insert record")
                    
            except Exception as e:
                print(f"   [ERROR] Failed to fix record {old_id}: {e}")
                # Try to restore the record if deletion succeeded but insert failed
                try:
                    supabase.table("listings").insert({**record, 'id': old_id}).execute()
                    print(f"   [RESTORE] Attempted to restore record with original ID {old_id}")
                except:
                    pass
        
        print()
        print("=" * 70)
        print(f"[SUCCESS] Fixed {fixed_count} out of {len(records)} records")
        print("=" * 70)
        
        # Now reset the sequence to ensure future inserts are correct
        print("\n5. Resetting sequence...")
        print("   Run this SQL in Supabase SQL Editor:")
        new_max_result = supabase.table("listings").select("id").order("id", desc=True).limit(1).execute()
        new_max_id = new_max_result.data[0]['id'] if new_max_result.data else current_max_id
        next_seq = new_max_id + 1
        
        print(f"\n   SELECT setval('listings_id_seq', {next_seq}, false);")
        print("\nThis ensures future inserts use sequential IDs.")
        print()
        
    except Exception as e:
        print(f"   [ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

