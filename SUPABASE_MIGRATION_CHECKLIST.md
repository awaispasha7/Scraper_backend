# Supabase Migration Checklist

## ✅ Migration Status

This checklist ensures all components are using the new Supabase instance.

### New Supabase Credentials
- **URL**: `https://jpojoxidogqrqeahdxmu.supabase.co`
- **Publishable Key**: `sb_publishable_I8MbJxM6pE2Nwf2DyAmFoA_GHU5PGfn`
- **Service Role Key**: `[GET FROM SUPABASE DASHBOARD]`

---

## 1. Backend Environment Variables

### For Local Development

Create/update `Scraper_backend/.env`:

```env
# Supabase Configuration (NEW INSTANCE)
SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# Alternative variable names (also supported)
SUPABASE_KEY=your_service_role_key_here

# Other required variables (keep existing values)
ATTOM_API_KEY=your_attom_api_key
MELISSA_API_KEY=your_melissa_api_key
BATCHDATA_API_KEY=your_batchdata_api_key
BATCHDATA_ENABLED=true
BATCHDATA_DAILY_LIMIT=50
API_URL=https://your-frontend-url.railway.app/api/listings/add
REAL_TIME_STORAGE=true
PORT=8080
```

**Important**: 
- Use the **service_role key** (NOT the publishable key) for backend
- Get the service_role key from: Supabase Dashboard → Settings → API → service_role key
- The key should start with `sb_service_role_`

### For Railway Deployment

1. Go to Railway Dashboard
2. Select your backend service
3. Navigate to **Variables** tab
4. Update or add these variables:

```
SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
```

5. **Redeploy** the backend service after updating variables

---

## 2. Frontend Environment Variables

### For Local Development

Create/update `SCraper_frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_I8MbJxM6pE2Nwf2DyAmFoA_GHU5PGfn
```

### For Vercel/Railway Frontend Deployment

1. Go to your deployment platform (Vercel/Railway)
2. Navigate to **Settings** → **Environment Variables**
3. Update or add:

```
NEXT_PUBLIC_SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_I8MbJxM6pE2Nwf2DyAmFoA_GHU5PGfn
```

4. **Redeploy** the frontend after updating variables

---

## 3. Component Checklist

All components read Supabase credentials from environment variables. Verify each component:

### ✅ Backend API Server (`api_server.py`)
- **Location**: `Scraper_backend/api_server.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_KEY` or `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update `.env` file or Railway variables

### ✅ FSBO Scraper (`forsalebyowner_selenium_scraper.py`)
- **Location**: `Scraper_backend/FSBO_Scraper/forsalebyowner_selenium_scraper.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables (from project root `.env`)
- **Action**: Update backend `.env` file

### ✅ Apartments Scraper (`apartments_scraper/pipelines.py`)
- **Location**: `Scraper_backend/Apartments_Scraper/apartments_scraper/pipelines.py`
- **Variables Used**: `SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
- **Status**: ✅ Reads from environment variables, supports multiple variable names
- **Action**: Update backend `.env` file

### ✅ Trulia Scraper (`trulia_scraper/pipelines/supabase_pipeline.py`)
- **Location**: `Scraper_backend/Trulia_Scraper/trulia_scraper/pipelines/supabase_pipeline.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ Redfin Scraper (`redfin_FSBO_backend/pipelines.py`)
- **Location**: `Scraper_backend/Redfin_Scraper/redfin_FSBO_backend/pipelines.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ Zillow FSBO Scraper (`zillow_FSBO_backend/supabase_pipeline.py`)
- **Location**: `Scraper_backend/Zillow_FSBO_Scraper/zillow_FSBO_backend/supabase_pipeline.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ Zillow FRBO Scraper (`zillow_scraper/pipelines/supabase_pipeline.py`)
- **Location**: `Scraper_backend/Zillow_FRBO_Scraper/zillow_scraper/pipelines/supabase_pipeline.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ Hotpads Scraper (`hotpads/pipelines.py`)
- **Location**: `Scraper_backend/Hotpads_Scraper/hotpads/pipelines.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ BatchData Worker (`batchdata_worker.py`)
- **Location**: `Scraper_backend/batchdata_worker.py`
- **Variables Used**: `SUPABASE_URL`, `SUPABASE_KEY` or `SUPABASE_SERVICE_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update backend `.env` file

### ✅ Frontend Dashboard (`lib/supabase-client.ts`, `lib/supabase.ts`)
- **Location**: `SCraper_frontend/lib/supabase-client.ts`, `SCraper_frontend/lib/supabase.ts`
- **Variables Used**: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Status**: ✅ Reads from environment variables
- **Action**: Update `.env.local` file or deployment platform variables

---

## 4. Verification Steps

### Step 1: Verify Backend Connection

1. **Check API Server**:
   ```bash
   cd Scraper_backend
   python api_server.py
   ```
   - Look for Supabase connection messages in logs
   - Should see: "Connected to Supabase" or similar

2. **Test API Endpoint**:
   ```bash
   curl http://localhost:8080/api/enrichment-stats
   ```
   - Should return enrichment stats from new database
   - If it returns error, check environment variables

### Step 2: Verify Frontend Connection

1. **Start Frontend**:
   ```bash
   cd SCraper_frontend
   npm run dev
   ```

2. **Check Browser Console**:
   - Open browser DevTools (F12)
   - Check for any Supabase connection errors
   - Should be able to log in and see data

3. **Test Dashboard**:
   - Navigate to dashboard
   - Verify listings are loading from new database
   - Check enrichment stats

### Step 3: Verify Scraper Connection

1. **Test FSBO Scraper** (uses Supabase):
   ```bash
   cd Scraper_backend
   python -m FSBO_Scraper.forsalebyowner_selenium_scraper
   ```
   - Check logs for "Connected to Supabase" message
   - Verify data is being written to new database

2. **Test Other Scrapers**:
   - Each scraper should connect to Supabase automatically
   - Check logs for connection messages
   - Verify data appears in new Supabase database

### Step 4: Verify Database Schema

1. **Go to Supabase Dashboard**:
   - Navigate to: https://supabase.com/dashboard/project/jpojoxidogqrqeahdxmu
   - Go to **Table Editor**

2. **Verify Tables Exist**:
   - ✅ `listings`
   - ✅ `trulia_listings`
   - ✅ `redfin_listings`
   - ✅ `zillow_fsbo_listings`
   - ✅ `zillow_frbo_listings`
   - ✅ `hotpads_listings`
   - ✅ `apartments_frbo`
   - ✅ `property_owners`
   - ✅ `property_owner_enrichment_state`
   - ✅ `addresses`
   - ✅ `scrape_metadata`
   - ✅ `scrape_state`

---

## 5. Common Issues & Solutions

### Issue: "Database not configured" error
**Solution**: 
- Check that `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set in backend `.env`
- Restart the backend server after updating `.env`

### Issue: "Missing Supabase environment variables" in frontend
**Solution**:
- Check that `.env.local` exists in `SCraper_frontend/` directory
- Verify variable names are exactly: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Restart the dev server after updating `.env.local`

### Issue: Scrapers not connecting to Supabase
**Solution**:
- Verify backend `.env` file has correct credentials
- Check that scrapers are reading from the correct `.env` file location
- Look for error messages in scraper logs

### Issue: Authentication errors or permission denied
**Solution**:
- Make sure you're using the **service_role key** (not publishable key) for backend
- Service role key should start with `sb_service_role_`
- Verify the key is correct in Supabase Dashboard

---

## 6. Migration Complete Checklist

- [ ] Updated `Scraper_backend/.env` with new Supabase credentials
- [ ] Updated Railway backend environment variables
- [ ] Updated `SCraper_frontend/.env.local` with new Supabase credentials
- [ ] Updated Vercel/Railway frontend environment variables
- [ ] Restarted backend API server
- [ ] Restarted frontend dev server (or redeployed)
- [ ] Verified backend API server connects to new Supabase
- [ ] Verified frontend dashboard loads data from new Supabase
- [ ] Tested at least one scraper to verify it writes to new Supabase
- [ ] Verified all tables exist in new Supabase database
- [ ] Verified authentication/login works with new Supabase

---

## 7. Next Steps After Migration

1. **Monitor Logs**: Watch for any connection errors in the first few hours
2. **Test All Scrapers**: Run each scraper once to ensure they connect properly
3. **Verify Data**: Check that new data appears in the new Supabase database
4. **Update Documentation**: Note the migration date and new project URL
5. **Clean Up**: Consider removing old Supabase credentials from old deployment (after verification)

---

## Quick Reference

### Environment Variable Summary

**Backend (All scrapers + API server)**:
- `SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co`
- `SUPABASE_SERVICE_KEY=sb_service_role_[YOUR_KEY]` (get from Supabase Dashboard)

**Frontend**:
- `NEXT_PUBLIC_SUPABASE_URL=https://jpojoxidogqrqeahdxmu.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_I8MbJxM6pE2Nwf2DyAmFoA_GHU5PGfn`

### Where to Get Service Role Key

1. Go to: https://supabase.com/dashboard/project/jpojoxidogqrqeahdxmu
2. Navigate to: **Settings** → **API**
3. Copy the **service_role** key (⚠️ Keep this secret!)

---

## Support

If you encounter issues:
1. Check the error messages in logs
2. Verify environment variables are set correctly
3. Verify the service_role key is correct
4. Check that the new Supabase project is active and accessible

