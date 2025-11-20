# Backend Deployment Guide

## Backend Components

1. **Python Scraper**: `forsalebyowner_selenium_scraper.py`
2. **Node.js Scripts**: 
   - `update_owner_names.js`
   - `update_mailing_addresses.js`

---

## Option 1: Deploy to Railway (Recommended)

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login
```bash
railway login
```

### Step 3: Initialize Project
```bash
cd fsdf
railway init
```

### Step 4: Create Procfile
Create `Procfile` in root directory:
```
worker: python forsalebyowner_selenium_scraper.py
```

### Step 5: Create runtime.txt
Create `runtime.txt`:
```
python-3.11
```

### Step 6: Deploy
```bash
railway up
```

### Step 7: Add Environment Variables
In Railway Dashboard → Variables:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
ATTOM_API_KEY=your_attom_api_key
MELISSA_API_KEY=your_melissa_api_key
```

---

## Option 2: Deploy to Render

### Step 1: Create render.yaml
Create `render.yaml` in root:
```yaml
services:
  - type: worker
    name: forsalebyowner-scraper
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python forsalebyowner_selenium_scraper.py
    envVars:
      - key: SUPABASE_URL
      - key: SUPABASE_KEY
      - key: ATTOM_API_KEY
      - key: MELISSA_API_KEY
```

### Step 2: Deploy via Render Dashboard
1. Go to render.com
2. New → Background Worker
3. Connect GitHub repository
4. Configure environment variables
5. Deploy

---

## Option 3: Deploy Node.js Scripts Separately

For `update_owner_names.js` and `update_mailing_addresses.js`:

### Deploy to Railway:
```bash
# Create Procfile
echo "worker: node update_owner_names.js" > Procfile

# Deploy
railway up
```

---

## Push Backend to Separate Git Repository

```bash
# Initialize git
cd fsdf
git init

# Create .gitignore
cat > .gitignore << EOF
node_modules/
__pycache__/
*.pyc
.env
.env.local
*.log
*.csv
*.json
!package.json
EOF

# Add files
git add forsalebyowner_selenium_scraper.py
git add requirements.txt
git add update_owner_names.js
git add update_mailing_addresses.js
git add package.json
git add .gitignore
git add Procfile
git add runtime.txt

# Commit
git commit -m "Initial backend commit"

# Add remote (create repo on GitHub first)
git remote add origin https://github.com/yourusername/forsalebyowner-backend.git

# Push
git push -u origin main
```

---

## Environment Variables Needed

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
ATTOM_API_KEY=your_attom_api_key
MELISSA_API_KEY=your_melissa_api_key
```

---

## Scheduled Jobs

For scheduled scraping, use:
- **Railway**: Cron jobs
- **Render**: Cron jobs
- **AWS Lambda**: EventBridge scheduler
- **GitHub Actions**: Scheduled workflows

