"""
Comprehensive diagnostic script for enrichment system.
"""
import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

print("=" * 60)
print("ENRICHMENT SYSTEM DIAGNOSTIC")
print("=" * 60)

# 1. Count remaining listings to process
print("\n--- 1. REMAINING LISTINGS TO PROCESS ---")
res = supabase.table("property_owner_enrichment_state") \
    .select("*", count="exact", head=True) \
    .eq("status", "never_checked") \
    .eq("locked", False) \
    .execute()
never_checked = res.count or 0
print(f"Never Checked (Pending): {never_checked}")

# 2. Count already processed
res2 = supabase.table("property_owner_enrichment_state") \
    .select("*", count="exact", head=True) \
    .eq("status", "enriched") \
    .execute()
enriched = res2.count or 0
print(f"Already Enriched: {enriched}")

res3 = supabase.table("property_owner_enrichment_state") \
    .select("*", count="exact", head=True) \
    .eq("status", "no_owner_data") \
    .execute()
no_data = res3.count or 0
print(f"No Owner Data Found: {no_data}")

# 3. Check FSBO listings that ALREADY have owner info
print("\n--- 2. FSBO LISTINGS WITH EXISTING OWNER INFO ---")
res_fsbo = supabase.table("listings") \
    .select("*", count="exact", head=True) \
    .not_.is_("owner_name", "null") \
    .neq("owner_name", "") \
    .execute()
fsbo_with_owner = res_fsbo.count or 0
print(f"FSBO listings with owner_name already: {fsbo_with_owner}")

# 4. Check sync-back status - enriched records that exist in property_owners
print("\n--- 3. SYNC-BACK STATUS ---")
res_owners = supabase.table("property_owners") \
    .select("*", count="exact", head=True) \
    .execute()
total_owners = res_owners.count or 0
print(f"Total records in property_owners: {total_owners}")

# 5. Sample of recent enriched - verify they have owner_info
print("\n--- 4. RECENT ENRICHED SAMPLE ---")
recent = supabase.table("property_owner_enrichment_state") \
    .select("address_hash, normalized_address, status, checked_at") \
    .eq("status", "enriched") \
    .not_.is_("checked_at", "null") \
    .order("checked_at", desc=True) \
    .limit(5) \
    .execute()

for r in recent.data:
    h = r['address_hash']
    owner_check = supabase.table("property_owners").select("owner_name").eq("address_hash", h).execute()
    has_owner = bool(owner_check.data)
    print(f"  {r['normalized_address'][:40]}... | Owner Saved: {has_owner}")

# 6. Pending entries with checked_at (BUG indicator)
print("\n--- 5. BUG CHECK: Pending entries WITH checked_at ---")
pending_bug = supabase.table("property_owner_enrichment_state") \
    .select("address_hash, status, checked_at") \
    .eq("status", "never_checked") \
    .not_.is_("checked_at", "null") \
    .limit(5) \
    .execute()
print(f"Pending entries with checked_at (should be 0): {len(pending_bug.data)}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
