# Railway Deployment Guide

## Quick Setup

1. **Create Railway Account**: Go to [railway.app](https://railway.app)

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your backend repository

3. **Configure Build Settings**:
   - Railway will auto-detect Python
   - Make sure these files are in root:
     - `Procfile` ✅
     - `runtime.txt` ✅
     - `requirements.txt` ✅
     - `railway.json` ✅

4. **Add Environment Variables**:
   In Railway Dashboard → Variables tab:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_service_role_key
   ATTOM_API_KEY=your_attom_api_key
   MELISSA_API_KEY=your_melissa_api_key
   API_URL=https://your-frontend-url.vercel.app/api/listings/add
   REAL_TIME_STORAGE=true
   ```

5. **Deploy**:
   - Railway will automatically build and deploy
   - Check logs for any errors

## Important Notes

- **Chrome/Chromium**: Railway will install Chrome automatically via buildpack
- **Headless Mode**: Scraper runs in headless mode by default (perfect for Railway)
- **Worker Type**: This is a background worker, not a web service

## Troubleshooting

### Error: "No start command found"
- Make sure `Procfile` exists in root directory
- Check that `Procfile` contains: `worker: python forsalebyowner_selenium_scraper.py`

### Error: "Chrome not found"
- Railway should install Chrome automatically
- If not, add to `nixpacks.toml`:
  ```toml
  [phases.install]
  cmds = ["apt-get update && apt-get install -y chromium chromium-driver"]
  ```

### Error: "Selenium WebDriver error"
- Make sure all dependencies are in `requirements.txt`
- Check that `webdriver-manager` is installed

## Scheduled Runs

To run scraper on a schedule:

1. **Railway Cron** (Recommended):
   - Go to Railway Dashboard → Project → Settings
   - Add Cron Job: `0 */12 * * *` (every 12 hours)

2. **GitHub Actions** (Alternative):
   - Create `.github/workflows/scraper.yml`
   - Schedule runs using cron syntax

## Monitoring

- Check Railway Dashboard → Deployments for build logs
- Check Railway Dashboard → Metrics for resource usage
- Check Railway Dashboard → Logs for runtime logs

