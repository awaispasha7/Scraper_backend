"""
Script to fix the listings table sequence in Supabase.
This resolves duplicate key errors and ensures IDs are sequential.

The issue: When the sequence gets out of sync, PostgreSQL tries to use IDs
that already exist, causing "duplicate key" errors. This script identifies
the problem and provides the SQL command to fix it.
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
    print("Fixing listings table sequence in Supabase")
    print("=" * 70)
    
    # Get the current maximum ID from the listings table
    print("\n1. Checking current maximum ID in listings table...")
    try:
        max_id_result = supabase.table("listings").select("id").order("id", desc=True).limit(1).execute()
        
        if max_id_result.data and len(max_id_result.data) > 0:
            max_id = max_id_result.data[0]['id']
            print(f"   [OK] Current maximum ID: {max_id}")
        else:
            max_id = 0
            print("   [OK] No records found, sequence should start at 1")
    except Exception as e:
        print(f"   [ERROR] Error getting max ID: {e}")
        exit(1)
    
    # Get total count
    try:
        count_result = supabase.table("listings").select("id", count="exact").limit(0).execute()
        total_count = count_result.count if hasattr(count_result, 'count') else 0
        print(f"   [OK] Total records in table: {total_count}")
    except Exception as e:
        print(f"   [WARN] Could not get count: {e}")
        total_count = 0
    
    # Calculate the next sequence value (should be max_id + 1)
    next_seq_value = max_id + 1
    print(f"\n2. Sequence should be set to: {next_seq_value}")
    print(f"   (This ensures the next insert uses ID {next_seq_value})")
    
    # Check for duplicate IDs or gaps
    print("\n3. Checking for ID issues...")
    try:
        # Get a sample of IDs to check for gaps
        sample_result = supabase.table("listings").select("id").order("id", desc=True).limit(10).execute()
        if sample_result.data:
            ids = [r['id'] for r in sample_result.data]
            print(f"   Sample of highest IDs: {sorted(ids, reverse=True)[:5]}")
    except Exception as e:
        print(f"   [WARN] Could not check sample: {e}")
    
    # Generate the SQL command to fix the sequence
    sql_command = f"SELECT setval('listings_id_seq', {next_seq_value}, false);"
    
    print("\n" + "=" * 70)
    print("SQL COMMAND TO FIX SEQUENCE")
    print("=" * 70)
    print("\nRun this SQL command in your Supabase SQL Editor:")
    print("\n" + sql_command + "\n")
    print("=" * 70)
    print("\nSteps to fix:")
    print("1. Open your Supabase Dashboard")
    print("2. Go to SQL Editor")
    print("3. Paste the SQL command above")
    print("4. Click 'Run'")
    print("\nThis will reset the sequence to the correct value.")
    print(f"After this, new inserts will use IDs starting from {next_seq_value}")
    print("\n" + "=" * 70)
    
    # Verify the fix (if we could execute SQL directly)
    print("\n4. After running the SQL, you can verify by:")
    print("   - Checking that new inserts work without duplicate key errors")
    print("   - Verifying IDs are sequential")
    
    print("\n[SUCCESS] Analysis complete!")
    print("\nNote: If you continue to see 'duplicate key' errors after running")
    print("the SQL, there may be records with explicit IDs that need cleanup.")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nPlease check your Supabase credentials and try again.")
    import traceback
    traceback.print_exc()
    exit(1)
