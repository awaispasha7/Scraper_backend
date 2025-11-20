# 🚀 Quick Deployment Guide

## Frontend Deploy (Vercel) - 5 Minutes

### Method 1: Vercel CLI (Fastest)
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Go to frontend directory
cd fsdf/frontend

# 3. Login to Vercel
vercel login

# 4. Deploy
vercel

# 5. Add environment variables in Vercel dashboard
```

### Method 2: GitHub + Vercel (Recommended)
```bash
# 1. Create new GitHub repo: forsalebyowner-frontend
# 2. Push frontend code
cd fsdf/frontend
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/forsalebyowner-frontend.git
git push -u origin main

# 3. Go to vercel.com → Import GitHub repo
# 4. Set root directory: frontend
# 5. Add environment variables
# 6. Deploy
```

---

## Backend Deploy (Railway) - 10 Minutes

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Go to root directory
cd fsdf

# 4. Initialize
railway init

# 5. Create Procfile (if not exists)
echo "worker: python forsalebyowner_selenium_scraper.py" > Procfile

# 6. Create runtime.txt
echo "python-3.11" > runtime.txt

# 7. Deploy
railway up

# 8. Add environment variables in Railway dashboard
```

---

## Environment Variables Needed

### Frontend (Vercel):
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `ATTOM_API_KEY`
- `MELISSA_API_KEY`

### Backend (Railway):
- `SUPABASE_URL`
- `SUPABASE_KEY` (service role key)
- `ATTOM_API_KEY`
- `MELISSA_API_KEY`

---

## Separate Git Repos

### Frontend Repo:
```bash
cd fsdf/frontend
git init
git add .
git commit -m "Frontend code"
git remote add origin https://github.com/yourusername/forsalebyowner-frontend.git
git push -u origin main
```

### Backend Repo:
```bash
cd fsdf
git init
git add forsalebyowner_selenium_scraper.py requirements.txt update_*.js package.json Procfile runtime.txt
git commit -m "Backend code"
git remote add origin https://github.com/yourusername/forsalebyowner-backend.git
git push -u origin main
```

---

## Need Help?
- Frontend issues: Check `DEPLOY_FRONTEND.md`
- Backend issues: Check `DEPLOY_BACKEND.md`
- Full guide: Check `DEPLOYMENT_GUIDE.md`

