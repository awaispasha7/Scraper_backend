# Deployment Guide - Frontend & Backend

## Overview
- **Frontend**: Next.js application (deploy to Vercel)
- **Backend**: Python scraper + Node.js scripts (deploy separately)

---

## 🚀 Frontend Deployment (Vercel)

### Step 1: Prepare Frontend for Deployment

1. **Navigate to frontend directory:**
```bash
cd fsdf/frontend
```

2. **Create `.env.production` file** (for production environment variables):
```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
ATTOM_API_KEY=your_attom_api_key
MELISSA_API_KEY=your_melissa_api_key
```

3. **Build test locally:**
```bash
npm run build
```

### Step 2: Deploy to Vercel

#### Option A: Using Vercel CLI
```bash
# Install Vercel CLI globally
npm i -g vercel

# Login to Vercel
vercel login

# Deploy from frontend directory
cd fsdf/frontend
vercel

# Follow prompts:
# - Set up and deploy? Yes
# - Which scope? Your account
# - Link to existing project? No
# - Project name? forsalebyowner-dashboard
# - Directory? ./
# - Override settings? No
```

#### Option B: Using Vercel Dashboard
1. Go to [vercel.com](https://vercel.com)
2. Click "New Project"
3. Import your Git repository
4. Set root directory to `frontend`
5. Add environment variables in Vercel dashboard
6. Deploy

### Step 3: Configure Environment Variables in Vercel
In Vercel Dashboard → Project Settings → Environment Variables:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `ATTOM_API_KEY`
- `MELISSA_API_KEY`

---

## 🔧 Backend Deployment

### Option 1: Python Scraper (Recommended: Railway/Render/Heroku)

#### For Railway:
1. Create `Procfile` in root directory:
```
worker: python forsalebyowner_selenium_scraper.py
```

2. Create `runtime.txt`:
```
python-3.11
```

3. Deploy:
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up
```

#### For Render:
1. Create `render.yaml` in root:
```yaml
services:
  - type: worker
    name: forsalebyowner-scraper
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python forsalebyowner_selenium_scraper.py
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
```

2. Deploy via Render Dashboard

### Option 2: Node.js Scripts (Same as Python)

Deploy Node.js scripts (`update_owner_names.js`, `update_mailing_addresses.js`) to:
- Railway
- Render
- Heroku
- AWS Lambda (for scheduled tasks)

---

## 📦 Separate Git Repositories (Recommended)

### Frontend Repository Setup:

```bash
# Create new repo for frontend
cd fsdf/frontend
git init
git add .
git commit -m "Initial frontend commit"
git remote add origin https://github.com/yourusername/forsalebyowner-frontend.git
git push -u origin main
```

### Backend Repository Setup:

```bash
# Create new repo for backend (from root)
cd fsdf
git init
git add forsalebyowner_selenium_scraper.py
git add requirements.txt
git add update_owner_names.js
git add update_mailing_addresses.js
git add package.json
git add .gitignore
git commit -m "Initial backend commit"
git remote add origin https://github.com/yourusername/forsalebyowner-backend.git
git push -u origin main
```

---

## 🔐 Environment Variables Checklist

### Frontend (.env.production):
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `ATTOM_API_KEY`
- `MELISSA_API_KEY`

### Backend:
- `SUPABASE_URL`
- `SUPABASE_KEY` (service role key)
- `ATTOM_API_KEY`
- `MELISSA_API_KEY`

---

## 📝 Deployment Checklist

### Frontend:
- [ ] Build test successful (`npm run build`)
- [ ] Environment variables configured
- [ ] Deployed to Vercel
- [ ] Custom domain configured (optional)
- [ ] API routes tested

### Backend:
- [ ] Python dependencies installed
- [ ] Environment variables configured
- [ ] Deployed to hosting service
- [ ] Scheduled jobs configured (if needed)
- [ ] Monitoring set up

---

## 🎯 Quick Deploy Commands

### Frontend (Vercel):
```bash
cd fsdf/frontend
vercel --prod
```

### Backend (Railway):
```bash
railway up
```

---

## 📞 Support
For issues, check:
- Vercel logs: Dashboard → Project → Deployments → View Logs
- Backend logs: Your hosting service dashboard

