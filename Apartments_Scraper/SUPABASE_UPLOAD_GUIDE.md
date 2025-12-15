# Supabase Upload Guide

This guide explains how to upload the apartments CSV data to Supabase.

## Prerequisites

1. **Supabase Account**: You need a Supabase project
   - Sign up at https://supabase.com
   - Create a new project

2. **Get Your Credentials**:
   - Go to your Supabase project dashboard
   - Navigate to Settings > API
   - Copy your:
     - **Project URL** (SUPABASE_URL)
     - **anon/public key** (SUPABASE_KEY) - for client-side access
     - Or **service_role key** (SUPABASE_KEY) - for server-side access (more permissions)

## Step 1: Create the Table in Supabase

### Option A: Using SQL Editor (Recommended)

1. Go to your Supabase dashboard
2. Navigate to **SQL Editor**
3. Click **New Query**
4. Copy and paste the contents of `supabase_table_schema.sql`
5. Click **Run** to execute the SQL

This will create:
- The `apartments_frbo_chicago` table
- Indexes for better performance
- Automatic timestamp updates
- Row Level Security policies

### Option B: Using Table Editor

1. Go to **Table Editor** in Supabase dashboard
2. Click **New Table**
3. Name it: `apartments_frbo_chicago`
4. Add columns manually (see schema below)

## Step 2: Install Dependencies

```powershell
pip install supabase
```

Or install all requirements:
```powershell
pip install -r requirements.txt
```

## Step 3: Set Environment Variables

### Windows PowerShell:
```powershell
$env:SUPABASE_URL="https://your-project-id.supabase.co"
$env:SUPABASE_KEY="your-anon-or-service-role-key"
```

### Windows CMD:
```cmd
set SUPABASE_URL=https://your-project-id.supabase.co
set SUPABASE_KEY=your-anon-or-service-role-key
```

### Linux/Mac:
```bash
export SUPABASE_URL="https://your-project-id.supabase.co"
export SUPABASE_KEY="your-anon-or-service-role-key"
```

### Or create a `.env` file:
Create a file named `.env` in the project root:
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

## Step 4: Run the Upload Script

```powershell
python upload_to_supabase.py
```

### Options:
```powershell
# Use custom CSV file
python upload_to_supabase.py --csv "path/to/your/file.csv"

# Use custom table name
python upload_to_supabase.py --table "my_table_name"

# Adjust batch size (default: 100)
python upload_to_supabase.py --batch-size 50
```

## Table Schema

The table `apartments_frbo_chicago` has the following columns:

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key (auto-increment) |
| listing_url | TEXT | Unique listing URL (unique constraint) |
| title | TEXT | Listing title |
| price | TEXT | Price information |
| beds | TEXT | Number of bedrooms |
| baths | TEXT | Number of bathrooms |
| sqft | TEXT | Square footage |
| owner_name | TEXT | Owner/manager name |
| owner_email | TEXT | Owner email |
| phone_numbers | TEXT | Contact phone numbers |
| full_address | TEXT | Complete address |
| street | TEXT | Street address |
| city | TEXT | City |
| state | TEXT | State |
| zip_code | TEXT | ZIP code |
| neighborhood | TEXT | Neighborhood name |
| description | TEXT | Full description |
| created_at | TIMESTAMP | Auto-set on insert |
| updated_at | TIMESTAMP | Auto-updated on change |

## Features

- **Upsert Logic**: If a listing with the same URL already exists, it will be updated instead of creating a duplicate
- **Batch Processing**: Uploads data in batches (default: 100 records) for better performance
- **Error Handling**: Continues uploading even if some records fail
- **Progress Tracking**: Shows progress during upload

## Troubleshooting

### "SUPABASE_URL not set" Error
- Make sure you've set the environment variable correctly
- Check that you're using the correct format (PowerShell vs CMD syntax)

### "Table does not exist" Error
- Make sure you've created the table in Supabase first (Step 1)
- Check that the table name matches (default: `apartments_frbo_chicago`)

### "Permission denied" Error
- Check your RLS (Row Level Security) policies
- You may need to use the `service_role` key instead of `anon` key
- Or adjust the RLS policies in Supabase dashboard

### "Duplicate key" Error
- This is normal - the script uses upsert, so duplicates are handled automatically
- The script will update existing records with the same `listing_url`

## Verifying the Upload

1. Go to Supabase dashboard > **Table Editor**
2. Select `apartments_frbo_chicago` table
3. You should see all your listings

Or query using SQL Editor:
```sql
SELECT COUNT(*) FROM apartments_frbo_chicago;
```

## Next Steps

After uploading, you can:
- Query the data using Supabase's SQL Editor
- Create API endpoints using Supabase's auto-generated REST API
- Build a frontend application using Supabase client libraries
- Set up real-time subscriptions for new listings


