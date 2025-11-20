# Backend Environment Variables for Railway

## Required Environment Variables

Railway Dashboard → Backend Service → Variables tab mein ye add karein:

```
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key

# API Keys
ATTOM_API_KEY=your_attom_api_key
MELISSA_API_KEY=your_melissa_api_key

# Frontend API URL (for scraper to send data)
API_URL=https://scraperfrontend-production.up.railway.app/api/listings/add

# Real-time storage (should be true)
REAL_TIME_STORAGE=true

# Port (Railway automatically sets this, but you can override)
PORT=8080
```

## Important Notes

1. **API_URL**: Backend scraper is URL ko use karta hai data frontend ko send karne ke liye
2. **REAL_TIME_STORAGE**: `true` hona chahiye taaki scraper real-time mein data send kare
3. **SUPABASE_KEY**: Service role key use karein (not anon key) for write permissions

## How to Add in Railway

1. Railway Dashboard mein jao
2. Backend service select karein
3. "Variables" tab click karein
4. "New Variable" click karein
5. Har variable add karein (upar wale list se)

## Verification

After adding variables, check:
- Backend logs mein `API_URL` dikhna chahiye
- Scraper trigger karne par data frontend ko send hona chahiye

