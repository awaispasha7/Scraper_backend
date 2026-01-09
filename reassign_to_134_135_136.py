"""
Automatically reassign the 3 records to IDs 134, 135, 136.
"""
import os
import json
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
    
    # Get records with IDs 1026, 1027, 1028
    print("\n1. Fetching records to reassign...")
    old_ids = [1026, 1027, 1028]
    new_ids = [134, 135, 136]
    records = []
    
    for old_id in old_ids:
        result = supabase.table("listings").select("*").eq("id", old_id).execute()
        if result.data and len(result.data) > 0:
            records.append(result.data[0])
            print(f"   [OK] Found ID {old_id}: {result.data[0].get('address', 'N/A')[:50]}")
        else:
            print(f"   [ERROR] Record with ID {old_id} not found!")
            exit(1)
    
    # Check if target IDs are available
    print("\n2. Checking target IDs...")
    for new_id in new_ids:
        result = supabase.table("listings").select("id").eq("id", new_id).execute()
        if result.data and len(result.data) > 0:
            print(f"   [ERROR] ID {new_id} is already taken!")
            exit(1)
        else:
            print(f"   [OK] ID {new_id} is available")
    
    print("\n3. Reassigning records...")
    
    # For each record: delete old, prepare data, adjust sequence, re-insert
    for i, record in enumerate(records):
        old_id = record['id']
        new_id = new_ids[i]
        address = record.get('address', 'N/A')
        
        print(f"\n   Record {i+1}: {address[:50]}")
        print(f"      Moving from ID {old_id} to ID {new_id}...")
        
        # Prepare data without auto-generated fields
        record_data = {k: v for k, v in record.items() if k not in ['id', 'created_at', 'updated_at']}
        
        try:
            # Don't delete yet - just prepare SQL
            print(f"      [PREPARE] Will delete ID {old_id} via SQL...")
            # delete_result = supabase.table("listings").delete().eq("id", old_id).execute()  # Commented out - do via SQL instead
            
            # Adjust sequence to allow inserting at new_id
            # We need to use SQL for this - generate SQL command
            seq_sql = f"SELECT setval('listings_id_seq', {new_id - 1}, false);"
            print(f"      [INFO] Run this SQL to adjust sequence: {seq_sql}")
            
            # Re-insert with explicit ID
            # Note: Supabase Python client doesn't easily allow explicit IDs
            # We need to use a workaround or SQL directly
            print(f"      [INSERT] Re-inserting with ID {new_id}...")
            
            # Try inserting - but first we need the sequence adjusted via SQL
            # Since we can't easily do that via Python client, we'll use SQL directly
            # Let's build a complete SQL statement
            
            # Escape single quotes in strings
            def escape_sql(value):
                if value is None:
                    return "NULL"
                if isinstance(value, (dict, list)):
                    return f"'{json.dumps(value).replace(chr(39), chr(39)+chr(39))}'::jsonb"
                return f"'{str(value).replace(chr(39), chr(39)+chr(39))}'"
            
            # Build INSERT statement
            fields = ['id', 'listing_link', 'address', 'price', 'beds', 'baths', 'square_feet', 
                     'time_of_post', 'owner_emails', 'owner_phones', 'owner_name', 'mailing_address']
            
            values = []
            values.append(str(new_id))  # Explicit ID
            for field in fields[1:]:  # Skip 'id'
                value = record_data.get(field)
                values.append(escape_sql(value))
            
            insert_sql = f"""
DELETE FROM listings WHERE id = {old_id};
SELECT setval('listings_id_seq', {new_id - 1}, false);
INSERT INTO listings ({', '.join(fields)}) VALUES ({', '.join(values)});
"""
            
            print(f"\n      Run this SQL:")
            print("      " + "-" * 66)
            print(insert_sql)
            print("      " + "-" * 66)
            
        except Exception as e:
            print(f"      [ERROR] Failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("After running all SQL commands, reset the sequence:")
    print("=" * 70)
    print("\nSELECT setval('listings_id_seq', (SELECT MAX(id) FROM listings));\n")
    
    # Actually, let me try to do it programmatically using a simpler approach
    # We can use UPDATE to change the ID directly, but we need to handle the sequence
    print("\n4. Attempting programmatic fix...")
    print("   (Using SQL via Supabase - this may require admin access)\n")
    
    # Generate complete SQL block
    print("=" * 70)
    print("COMPLETE SQL TO RUN IN SUPABASE SQL EDITOR:")
    print("=" * 70)
    print()
    
    for i, record in enumerate(records):
        old_id = record['id']
        new_id = new_ids[i]
        
        # Build proper INSERT with all fields
        insert_fields = []
        insert_values = []
        
        # Add explicit ID
        insert_fields.append('id')
        insert_values.append(str(new_id))
        
        # Add all other fields from record_data
        for field, value in record_data.items():
            insert_fields.append(field)
            if value is None:
                insert_values.append('NULL')
            elif isinstance(value, (dict, list)):
                insert_values.append(f"'{json.dumps(value).replace(chr(39), chr(39)+chr(39))}'::jsonb")
            elif isinstance(value, bool):
                insert_values.append('true' if value else 'false')
            elif isinstance(value, (int, float)):
                insert_values.append(str(value))
            else:
                escaped = str(value).replace(chr(39), chr(39)+chr(39))
                insert_values.append(f"'{escaped}'")
        
        sql_block = f"""
-- Reassign record from ID {old_id} to {new_id}
DELETE FROM listings WHERE id = {old_id};
SELECT setval('listings_id_seq', {new_id - 1}, false);
INSERT INTO listings ({', '.join(insert_fields)}) VALUES ({', '.join(insert_values)});
"""
        print(sql_block)
    
    print("\n-- Finally, reset sequence to max ID")
    print("SELECT setval('listings_id_seq', (SELECT MAX(id) FROM listings));")
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

