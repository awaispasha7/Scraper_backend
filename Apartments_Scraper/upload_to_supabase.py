"""
Script to upload apartments CSV data to Supabase.
Creates a table and inserts all listings from the CSV file.
"""

import os
import csv
import sys
from supabase import create_client, Client
from typing import List, Dict, Optional

# Fix Windows console encoding for emoji support
def safe_print(*args, **kwargs):
    """Print function that handles encoding errors gracefully."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If encoding fails, replace emojis with text
        text = ' '.join(str(arg) for arg in args)
        # Replace common emojis with text equivalents
        text = text.replace('📤', '[UPLOAD]')
        text = text.replace('🔌', '[CONNECT]')
        text = text.replace('✅', '[OK]')
        text = text.replace('❌', '[ERROR]')
        text = text.replace('⚠️', '[WARNING]')
        text = text.replace('ℹ️', '[INFO]')
        text = text.replace('🏗️', '[BUILD]')
        print(text, **kwargs)

# Try to fix encoding, but use safe_print if it fails
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError, TypeError):
        # Python < 3.7 or reconfigure failed, use safe_print
        import builtins
        builtins.print = safe_print


def load_env_file():
    """Load environment variables from .env file if it exists."""
    # Check multiple possible locations for .env file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, '.env'),  # Same directory as script
        os.path.join(os.path.dirname(script_dir), '.env'),  # Parent directory
        os.path.join(os.path.dirname(os.path.dirname(script_dir)), '.env'),  # Grandparent directory
        os.path.join(os.path.expanduser('~'), '.env'),  # Home directory
    ]
    
    env_path = None
    for path in possible_paths:
        if os.path.exists(path):
            env_path = path
            break
    
    if env_path:
        print(f"📄 Found .env file at: {env_path}")
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                loaded_count = 0
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and value and key not in os.environ:
                            os.environ[key] = value
                            loaded_count += 1
                if loaded_count > 0:
                    print(f"✅ Loaded {loaded_count} environment variable(s) from .env file")
                else:
                    print(f"⚠️  .env file found but no variables loaded (may already be set or file is empty)")
        except Exception as e:
            print(f"⚠️  Error reading .env file: {e}")
    else:
        print(f"ℹ️  .env file not found. Checked locations:")
        for path in possible_paths:
            print(f"   - {path}")


def get_supabase_client(supabase_url=None, supabase_key=None) -> Client:
    """Create and return Supabase client.
    
    Args:
        supabase_url: Optional Supabase URL (overrides env variable)
        supabase_key: Optional Supabase key (overrides env variable)
    """
    # Try to load from .env file first
    load_env_file()
    
    # Use provided values or get from environment
    # Check multiple possible variable names (support Next.js style and standard)
    supabase_url = (
        supabase_url or 
        os.getenv("SUPABASE_URL") or 
        os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    )
    
    supabase_key = (
        supabase_key or 
        os.getenv("SUPABASE_KEY") or 
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or 
        os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    
    if not supabase_url:
        raise ValueError(
            "SUPABASE_URL environment variable is not set.\n"
            "Please set it using one of these methods:\n"
            "1. Command line: --supabase-url 'https://your-project.supabase.co'\n"
            "2. Environment variable: $env:SUPABASE_URL='https://your-project.supabase.co'\n"
            "3. Create a .env file with: SUPABASE_URL=https://your-project.supabase.co\n"
            "   (or NEXT_PUBLIC_SUPABASE_URL for Next.js projects)"
        )
    if not supabase_key:
        raise ValueError(
            "SUPABASE_KEY environment variable is not set.\n"
            "Please set it using one of these methods:\n"
            "1. Command line: --supabase-key 'your-anon-key'\n"
            "2. Environment variable: $env:SUPABASE_KEY='your-anon-key'\n"
            "3. Create a .env file with: SUPABASE_KEY=your-anon-key\n"
            "   (or SUPABASE_SERVICE_ROLE_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY)"
        )
    
    return create_client(supabase_url, supabase_key)


def create_table_sql() -> str:
    """Return SQL to create the apartments table."""
    return """
    CREATE TABLE IF NOT EXISTS apartments_frbo_chicago (
        id BIGSERIAL PRIMARY KEY,
        listing_url TEXT UNIQUE NOT NULL,
        title TEXT,
        price TEXT,
        beds TEXT,
        baths TEXT,
        sqft TEXT,
        owner_name TEXT,
        owner_email TEXT,
        phone_numbers TEXT,
        full_address TEXT,
        street TEXT,
        city TEXT,
        state TEXT,
        zip_code TEXT,
        neighborhood TEXT,
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create index on listing_url for faster lookups
    CREATE INDEX IF NOT EXISTS idx_apartments_listing_url ON apartments_frbo_chicago(listing_url);
    
    -- Create index on city for filtering
    CREATE INDEX IF NOT EXISTS idx_apartments_city ON apartments_frbo_chicago(city);
    
    -- Create index on zip_code for filtering
    CREATE INDEX IF NOT EXISTS idx_apartments_zip_code ON apartments_frbo_chicago(zip_code);
    """


def read_csv_file(csv_path: str) -> List[Dict]:
    """Read CSV file and return list of dictionaries."""
    listings = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Clean empty strings and convert to None for better database handling
            cleaned_row = {}
            for key, value in row.items():
                if value and value.strip():
                    cleaned_row[key] = value.strip()
                else:
                    cleaned_row[key] = None
            listings.append(cleaned_row)
    return listings


def upload_to_supabase(csv_path: str, table_name: str = "apartments_frbo_chicago", batch_size: int = 100, supabase_url: str = None, supabase_key: str = None):
    """
    Upload CSV data to Supabase.
    
    Args:
        csv_path: Path to CSV file
        table_name: Name of the table in Supabase
        batch_size: Number of records to insert per batch
        supabase_url: Optional Supabase URL (overrides env variable)
        supabase_key: Optional Supabase key (overrides env variable)
    """
    print("=" * 70)
    print("📤 UPLOADING APARTMENTS DATA TO SUPABASE")
    print("=" * 70)
    print()
    
    # Check if CSV file exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Create Supabase client
    print("🔌 Connecting to Supabase...")
    print()
    try:
        supabase = get_supabase_client(supabase_url, supabase_key)
        print("✅ Connected to Supabase")
        print()
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        print()
        print("💡 Make sure you have set the following environment variables:")
        print("   - SUPABASE_URL: Your Supabase project URL")
        print("   - SUPABASE_KEY: Your Supabase anon/service_role key")
        print()
        print("   Option 1: Create a .env file in the same directory as this script:")
        print("   SUPABASE_URL=https://your-project.supabase.co")
        print("   SUPABASE_KEY=your-anon-key")
        print()
        print("   Option 2: Set environment variables (PowerShell):")
        print("   $env:SUPABASE_URL='https://your-project.supabase.co'")
        print("   $env:SUPABASE_KEY='your-anon-key'")
        print()
        raise
    
    # Read CSV file
    print(f"📄 Reading CSV file: {csv_path}")
    listings = read_csv_file(csv_path)
    print(f"✅ Found {len(listings)} listings in CSV")
    print()
    
    # Create table using SQL (if needed)
    print(f"🏗️  Creating/verifying table '{table_name}'...")
    try:
        # Execute SQL to create table
        # Note: Supabase Python client doesn't have direct SQL execution
        # We'll try to insert and let it fail if table doesn't exist
        # Or you can create the table manually in Supabase dashboard
        print("   ℹ️  Note: Table should be created manually in Supabase dashboard")
        print("   ℹ️  Or use the SQL provided in the script output")
        print()
    except Exception as e:
        print(f"   ⚠️  Could not verify table creation: {e}")
        print("   ℹ️  You may need to create the table manually in Supabase dashboard")
        print()
    
    # Upload data in batches
    print(f"📤 Uploading {len(listings)} listings to Supabase...")
    print(f"   Batch size: {batch_size}")
    print()
    
    uploaded_count = 0
    skipped_count = 0
    error_count = 0
    
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(listings) + batch_size - 1) // batch_size
        
        print(f"   📦 Processing batch {batch_num}/{total_batches} ({len(batch)} listings)...", end=" ")
        
        try:
            # Insert batch - use upsert to handle duplicates
            result = supabase.table(table_name).upsert(
                batch,
                on_conflict="listing_url"  # Update if listing_url already exists
            ).execute()
            
            # Count successful inserts
            # Note: Supabase returns the inserted data, so we can count it
            batch_uploaded = len(batch)
            uploaded_count += batch_uploaded
            
            print(f"✅ Uploaded {batch_uploaded} listings")
            
        except Exception as e:
            error_count += len(batch)
            print(f"❌ Error: {e}")
            # Try inserting one by one to see which ones fail
            for listing in batch:
                try:
                    supabase.table(table_name).upsert(
                        listing,
                        on_conflict="listing_url"
                    ).execute()
                    uploaded_count += 1
                except Exception as single_error:
                    skipped_count += 1
                    print(f"      ⚠️  Skipped: {listing.get('listing_url', 'Unknown URL')[:50]}... - {single_error}")
    
    print()
    print("=" * 70)
    print("📊 UPLOAD SUMMARY")
    print("=" * 70)
    print(f"✅ Successfully uploaded: {uploaded_count} listings")
    if skipped_count > 0:
        print(f"⚠️  Skipped: {skipped_count} listings")
    if error_count > 0:
        print(f"❌ Errors: {error_count} listings")
    print(f"📄 Total in CSV: {len(listings)}")
    print()
    print("=" * 70)
    
    # Print SQL for manual table creation
    print()
    print("💡 SQL TO CREATE TABLE (if needed):")
    print("-" * 70)
    print(create_table_sql())
    print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Upload apartments CSV data to Supabase"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="output/apartments_frbo_chicago-il.csv",
        help="Path to CSV file (default: output/apartments_frbo_chicago-il.csv)"
    )
    parser.add_argument(
        "--table",
        type=str,
        default="apartments_frbo_chicago",
        help="Supabase table name (default: apartments_frbo_chicago)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records per batch (default: 100)"
    )
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=None,
        help="Supabase project URL (overrides environment variable)"
    )
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=None,
        help="Supabase API key (overrides environment variable)"
    )
    
    args = parser.parse_args()
    
    # Convert relative path to absolute
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        # Get script directory and construct path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, csv_path)
    
    try:
        upload_to_supabase(csv_path, args.table, args.batch_size, args.supabase_url, args.supabase_key)
        print("✅ Upload completed successfully!")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

