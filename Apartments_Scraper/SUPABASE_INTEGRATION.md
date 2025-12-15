# Supabase Integration Guide

This guide explains how the scraper automatically uploads data to Supabase.

## Overview

The scraper now has **automatic Supabase integration** built-in. When you run the scraper, it will:
1. ✅ Save listings to CSV file (as before)
2. ✅ **Automatically upload listings to Supabase** (new!)

## How It Works

### Automatic Upload During Scraping

The `SupabasePipeline` automatically:
- Connects to Supabase when the scraper starts
- Uploads each listing to Supabase as it's scraped
- Uses **upsert** (update if exists, insert if new) based on `listing_url`
- Handles errors gracefully - scraping continues even if Supabase upload fails
- Uploads in batches for better performance

### Pipeline Priority

Pipelines run in this order:
1. **CSV Pipeline** (priority 300) - Saves to CSV file first
2. **Supabase Pipeline** (priority 400) - Then uploads to Supabase

This ensures CSV is always saved, even if Supabase upload fails.

## Setup

### Step 1: Create Table in Supabase

Run the SQL script in Supabase SQL Editor:

```sql
-- Copy and paste the contents of supabase_table_schema.sql
-- Or run it directly in Supabase Dashboard > SQL Editor
```

### Step 2: Set Environment Variables

Add your Supabase credentials to your `.env` file:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

**Where to find your credentials:**
1. Go to your Supabase project dashboard
2. Navigate to **Settings > API**
3. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon/public key** → `SUPABASE_KEY` (for client-side)
   - Or **service_role key** → `SUPABASE_KEY` (for server-side, more permissions)

### Step 3: Install Dependencies

```powershell
pip install supabase
```

## Usage

### Running the Scraper

Just run the scraper as usual - Supabase upload happens automatically:

```powershell
cd "C:\Users\hp\Desktop\apartments home\apartments\apartments"
scrapy crawl apartments_frbo -a city="chicago-il" -a resume=true
```

**What happens:**
- ✅ Listings are saved to CSV file
- ✅ Listings are automatically uploaded to Supabase
- ✅ Duplicates are handled (updates existing, inserts new)

### Manual CSV Upload (Optional)

If you want to upload existing CSV data to Supabase:

```powershell
python upload_to_supabase.py --csv output/apartments_frbo_chicago-il.csv
```

This is useful for:
- Initial bulk upload of existing CSV data
- Re-uploading after CSV updates
- Uploading data from a different CSV file

## Features

### ✅ Automatic Updates

- New listings → Inserted into Supabase
- Existing listings → Updated in Supabase (based on `listing_url`)
- No duplicates → `listing_url` is unique

### ✅ Error Handling

- If Supabase credentials are missing → Pipeline disables, scraping continues
- If Supabase connection fails → Pipeline disables, scraping continues
- If individual upload fails → Error logged, scraping continues
- CSV is always saved regardless of Supabase status

### ✅ Batch Uploads

- Items are uploaded in batches of 10 for better performance
- Remaining items are uploaded when scraper closes

## Monitoring

### During Scraping

The scraper logs Supabase activity:

```
✅ Supabase pipeline enabled - connected to https://your-project.supabase.co
📊 Table: apartments_frbo_chicago
📤 Uploaded 10 items to Supabase (total: 50)
```

### After Scraping

Summary is logged when scraper closes:

```
📊 Supabase upload summary:
   ✅ Successfully uploaded: 705 listings
```

## Troubleshooting

### Pipeline Not Enabled

**Symptom:** No Supabase logs during scraping

**Solution:**
1. Check `.env` file has `SUPABASE_URL` and `SUPABASE_KEY`
2. Verify credentials are correct
3. Check Supabase project is active

### Upload Errors

**Symptom:** Errors in logs like "Error uploading batch to Supabase"

**Solutions:**
1. Check table exists in Supabase
2. Verify table schema matches CSV columns
3. Check RLS (Row Level Security) policies allow inserts
4. Try using `service_role` key instead of `anon` key

### Missing Listings

**Symptom:** Some listings not in Supabase

**Solution:**
1. Check scraper logs for upload errors
2. Run manual upload: `python upload_to_supabase.py`
3. Check Supabase logs in dashboard

## Table Schema

The table `apartments_frbo_chicago` has these columns:

- `id` - Auto-increment primary key
- `listing_url` - Unique identifier (used for upsert)
- `title`, `price`, `beds`, `baths`, `sqft`
- `owner_name`, `owner_email`, `phone_numbers`
- `full_address`, `street`, `city`, `state`, `zip_code`, `neighborhood`
- `description`
- `created_at`, `updated_at` - Auto-managed timestamps

## Next Steps

1. ✅ Create table in Supabase (run SQL script)
2. ✅ Add credentials to `.env` file
3. ✅ Run scraper - data uploads automatically!
4. ✅ Check Supabase dashboard to verify data

## Notes

- Supabase pipeline is **optional** - scraping works without it
- CSV file is always created regardless of Supabase status
- Use `service_role` key for full permissions (bypasses RLS)
- Use `anon` key for client-side access (respects RLS policies)

